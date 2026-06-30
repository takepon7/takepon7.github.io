from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, cast

from gitai_phase0.puzzle import (
    CatalogObject,
    PairProposal,
    PairProposalStatus,
    build_pair_proposal_key,
    normalize_proposed_label,
)


class ObjectCatalogRepository:
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._objects = [
            CatalogObject.from_dict(item)
            for item in payload.get("objects", ())
        ]
        self._by_id = {item.object_id: item for item in self._objects}
        self._by_label: dict[str, CatalogObject] = {}
        for item in self._objects:
            self._by_label.setdefault(normalize_proposed_label(item.canonical_label), item)
            for alias in item.aliases:
                self._by_label.setdefault(normalize_proposed_label(alias), item)

    def list(self) -> list[CatalogObject]:
        return list(self._objects)

    def get(self, object_id: str) -> CatalogObject:
        try:
            return self._by_id[object_id]
        except KeyError as exc:
            raise KeyError(f"Unknown object_id: {object_id}") from exc

    def find_by_label(self, label: str) -> CatalogObject | None:
        try:
            normalized = normalize_proposed_label(label)
        except ValueError:
            return None
        return self._by_label.get(normalized)


class SqlitePairProposalRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init_schema()

    def save(self, proposal: PairProposal) -> None:
        self.save_or_support(proposal)

    def save_or_support(self, proposal: PairProposal) -> PairProposal:
        with self._connect() as conn:
            row = conn.execute(
                """
                select proposal_id, pair_key, user_id, base_label, target_label,
                       base_object_id, target_object_id, status, rejection_reasons,
                       difficulty_prior, hard_negative_ids, support_count,
                       created_at, last_supported_at, reviewer_id, review_note,
                       reviewed_at
                from pair_proposals
                where pair_key = ?
                order by created_at asc, proposal_id asc
                limit 1
                """,
                (proposal.pair_key,),
            ).fetchone()
            if row is not None:
                existing = pair_proposal_from_row(row)
                supported = replace(
                    existing,
                    support_count=existing.support_count + 1,
                    last_supported_at=proposal.last_supported_at,
                )
                conn.execute(
                    """
                    update pair_proposals
                    set support_count = ?, last_supported_at = ?
                    where proposal_id = ?
                    """,
                    (
                        supported.support_count,
                        supported.last_supported_at.isoformat(),
                        supported.proposal_id,
                    ),
                )
                return supported
            conn.execute(
                """
                insert into pair_proposals (
                    proposal_id, pair_key, user_id, base_label, target_label,
                    base_object_id, target_object_id, status, rejection_reasons,
                    difficulty_prior, hard_negative_ids, support_count,
                    created_at, last_supported_at, reviewer_id, review_note,
                    reviewed_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.pair_key,
                    proposal.user_id,
                    proposal.base_label,
                    proposal.target_label,
                    proposal.base_object_id,
                    proposal.target_object_id,
                    proposal.status,
                    json.dumps(list(proposal.rejection_reasons), ensure_ascii=False),
                    proposal.difficulty_prior,
                    json.dumps(list(proposal.hard_negative_ids), ensure_ascii=False),
                    proposal.support_count,
                    proposal.created_at.isoformat(),
                    proposal.last_supported_at.isoformat(),
                    proposal.reviewer_id,
                    proposal.review_note,
                    proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
                ),
            )
        return proposal

    def get(self, proposal_id: str) -> PairProposal:
        with self._connect() as conn:
            row = conn.execute(
                """
                select proposal_id, pair_key, user_id, base_label, target_label,
                       base_object_id, target_object_id, status, rejection_reasons,
                       difficulty_prior, hard_negative_ids, support_count,
                       created_at, last_supported_at, reviewer_id, review_note,
                       reviewed_at
                from pair_proposals
                where proposal_id = ?
                """,
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown pair proposal: {proposal_id}")
        return pair_proposal_from_row(row)

    def review(self, proposal: PairProposal) -> PairProposal:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update pair_proposals
                set status = ?,
                    rejection_reasons = ?,
                    reviewer_id = ?,
                    review_note = ?,
                    reviewed_at = ?
                where proposal_id = ?
                """,
                (
                    proposal.status,
                    json.dumps(list(proposal.rejection_reasons), ensure_ascii=False),
                    proposal.reviewer_id,
                    proposal.review_note,
                    proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
                    proposal.proposal_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown pair proposal: {proposal.proposal_id}")
        return proposal

    def list(
        self,
        limit: int = 20,
        status: PairProposalStatus | None = None,
    ) -> list[PairProposal]:
        query = """
            select proposal_id, pair_key, user_id, base_label, target_label,
                   base_object_id, target_object_id, status, rejection_reasons,
                   difficulty_prior, hard_negative_ids, support_count,
                   created_at, last_supported_at, reviewer_id, review_note,
                   reviewed_at
            from pair_proposals
            """
        params: list[object] = []
        if status:
            query += " where status = ?"
            params.append(status)
        query += """
             order by support_count desc,
                      coalesce(last_supported_at, created_at) desc,
                      created_at desc,
                      proposal_id desc
             limit ?
            """
        params.append(max(1, min(limit, 100)))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [pair_proposal_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists pair_proposals (
                    proposal_id text primary key,
                    pair_key text not null default '',
                    user_id text not null,
                    base_label text not null,
                    target_label text not null,
                    base_object_id text not null default '',
                    target_object_id text not null default '',
                    status text not null,
                    rejection_reasons text not null,
                    difficulty_prior real,
                    hard_negative_ids text not null,
                    support_count integer not null default 1,
                    created_at text not null,
                    last_supported_at text,
                    reviewer_id text not null default '',
                    review_note text not null default '',
                    reviewed_at text
                )
                """
            )
            self._ensure_column(conn, "pair_key", "text not null default ''")
            self._ensure_column(conn, "support_count", "integer not null default 1")
            self._ensure_column(conn, "last_supported_at", "text")
            self._ensure_column(conn, "reviewer_id", "text not null default ''")
            self._ensure_column(conn, "review_note", "text not null default ''")
            self._ensure_column(conn, "reviewed_at", "text")
            self._backfill_pair_proposal_metadata(conn)
            self._collapse_duplicate_pair_keys(conn)
            conn.execute(
                "create index if not exists idx_pair_proposals_status_created on pair_proposals (status, created_at desc)"
            )
            conn.execute(
                """
                create index if not exists idx_pair_proposals_status_support
                on pair_proposals (status, support_count desc, last_supported_at desc)
                """
            )
            conn.execute(
                "create index if not exists idx_pair_proposals_pair_key on pair_proposals (pair_key)"
            )

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {str(row["name"]) for row in conn.execute("pragma table_info(pair_proposals)")}
        if name not in columns:
            conn.execute(f"alter table pair_proposals add column {name} {definition}")

    def _backfill_pair_proposal_metadata(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            update pair_proposals
            set last_supported_at = created_at
            where last_supported_at is null or last_supported_at = ''
            """
        )
        rows = conn.execute(
            """
            select proposal_id, base_label, target_label, base_object_id, target_object_id
            from pair_proposals
            where pair_key is null or pair_key = ''
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "update pair_proposals set pair_key = ? where proposal_id = ?",
                (pair_key_from_row(row), row["proposal_id"]),
            )

    def _collapse_duplicate_pair_keys(self, conn: sqlite3.Connection) -> None:
        groups = conn.execute(
            """
            select pair_key,
                   sum(support_count) as support_count,
                   max(coalesce(last_supported_at, created_at)) as last_supported_at
            from pair_proposals
            where pair_key <> ''
            group by pair_key
            having count(*) > 1
            """
        ).fetchall()
        for group in groups:
            rows = conn.execute(
                """
                select proposal_id
                from pair_proposals
                where pair_key = ?
                order by created_at asc, proposal_id asc
                """,
                (group["pair_key"],),
            ).fetchall()
            keep_id = str(rows[0]["proposal_id"])
            drop_ids = [str(row["proposal_id"]) for row in rows[1:]]
            conn.execute(
                """
                update pair_proposals
                set support_count = ?, last_supported_at = ?
                where proposal_id = ?
                """,
                (
                    int(group["support_count"] or 1),
                    str(group["last_supported_at"]),
                    keep_id,
                ),
            )
            conn.executemany(
                "delete from pair_proposals where proposal_id = ?",
                [(proposal_id,) for proposal_id in drop_ids],
            )


def pair_proposal_from_row(row: sqlite3.Row) -> PairProposal:
    created_at = datetime.fromisoformat(str(row["created_at"]))
    last_supported_at_value = row_value(row, "last_supported_at", None)
    reviewed_at_value = row_value(row, "reviewed_at", None)
    return PairProposal(
        proposal_id=str(row["proposal_id"]),
        pair_key=str(row_value(row, "pair_key", pair_key_from_row(row))),
        user_id=str(row["user_id"]),
        base_label=str(row["base_label"]),
        target_label=str(row["target_label"]),
        base_object_id=str(row["base_object_id"]),
        target_object_id=str(row["target_object_id"]),
        status=cast(PairProposalStatus, str(row["status"])),
        rejection_reasons=tuple(str(item) for item in json.loads(str(row["rejection_reasons"]))),
        difficulty_prior=(
            None if row["difficulty_prior"] is None else float(row["difficulty_prior"])
        ),
        hard_negative_ids=tuple(str(item) for item in json.loads(str(row["hard_negative_ids"]))),
        support_count=int(row_value(row, "support_count", 1) or 1),
        created_at=created_at,
        last_supported_at=(
            created_at
            if last_supported_at_value is None or str(last_supported_at_value) == ""
            else datetime.fromisoformat(str(last_supported_at_value))
        ),
        reviewer_id=str(row_value(row, "reviewer_id", "") or ""),
        review_note=str(row_value(row, "review_note", "") or ""),
        reviewed_at=(
            None
            if reviewed_at_value is None or str(reviewed_at_value) == ""
            else datetime.fromisoformat(str(reviewed_at_value))
        ),
    )


def row_value(row: sqlite3.Row, key: str, default: Any) -> Any:
    if key not in row.keys():
        return default
    return row[key]


def pair_key_from_row(row: sqlite3.Row) -> str:
    try:
        return build_pair_proposal_key(
            base_label=str(row["base_label"]),
            target_label=str(row["target_label"]),
            base_object_id=str(row["base_object_id"]),
            target_object_id=str(row["target_object_id"]),
        )
    except ValueError:
        return f"proposal:{row['proposal_id']}"
