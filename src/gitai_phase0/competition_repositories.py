from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

from gitai_phase0.competition import (
    DEFAULT_SEASON_ID,
    LeaderboardEntry,
    LeaderboardKind,
    PlayerIdentity,
    RateLimitDecision,
    SubmissionRecord,
    normalize_friend_code,
    normalize_season_id,
    rank_records,
)


class SqliteSubmissionRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init_schema()

    def save(self, record: SubmissionRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into submissions (
                    submission_id, season_id, puzzle_date, pair_id, ref_version,
                    user_id, display_name, image_hash, image_ref, friend_code, stroke_count,
                    score, percentile, raw, bucket, ocr_cheat, moderation,
                    model_version, created_at, stroke_log_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.submission_id,
                    record.season_id,
                    record.puzzle_date.isoformat(),
                    record.pair_id,
                    record.ref_version,
                    record.player.user_id,
                    record.player.display_name,
                    record.image_hash,
                    record.image_ref,
                    record.friend_code,
                    record.stroke_count,
                    record.score,
                    record.percentile,
                    record.raw,
                    record.bucket,
                    int(record.ocr_cheat),
                    record.moderation,
                    record.model_version,
                    record.created_at.isoformat(),
                    encode_stroke_log(record.stroke_log),
                ),
            )

    def seed(self, records: list[SubmissionRecord]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                insert or ignore into submissions (
                    submission_id, season_id, puzzle_date, pair_id, ref_version,
                    user_id, display_name, image_hash, image_ref, friend_code, stroke_count,
                    score, percentile, raw, bucket, ocr_cheat, moderation,
                    model_version, created_at, stroke_log_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.submission_id,
                        record.season_id,
                        record.puzzle_date.isoformat(),
                        record.pair_id,
                        record.ref_version,
                        record.player.user_id,
                        record.player.display_name,
                        record.image_hash,
                        record.image_ref,
                        record.friend_code,
                        record.stroke_count,
                        record.score,
                        record.percentile,
                        record.raw,
                        record.bucket,
                        int(record.ocr_cheat),
                        record.moderation,
                        record.model_version,
                        record.created_at.isoformat(),
                        encode_stroke_log(record.stroke_log),
                    )
                    for record in records
                ],
            )
            conn.executemany(
                """
                update submissions
                set image_ref = ?
                where submission_id = ? and image_ref = ''
                """,
                [(record.image_ref, record.submission_id) for record in records],
            )

    def leaderboard(
        self,
        puzzle_date: date,
        season_id: str = DEFAULT_SEASON_ID,
        limit: int = 20,
        kind: LeaderboardKind = "score",
        friend_code: str = "",
    ) -> list[LeaderboardEntry]:
        query = """
            select submission_id, season_id, puzzle_date, pair_id, ref_version, user_id, display_name,
                   image_hash, image_ref, friend_code, stroke_count, score, percentile, raw, bucket, ocr_cheat,
                   moderation, model_version, created_at, stroke_log_json
            from submissions
            where puzzle_date = ? and season_id = ?
            """
        params = [puzzle_date.isoformat(), normalize_season_id(season_id) or DEFAULT_SEASON_ID]
        if kind == "friend":
            query += " and friend_code = ?"
            params.append(normalize_friend_code(friend_code))
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        records = [record_from_row(row) for row in rows]
        rank_kind: LeaderboardKind = "score" if kind == "friend" else kind
        vote_counts = self._funny_vote_counts([record.submission_id for record in records]) if kind == "funny" else {}
        return rank_records(records, kind=rank_kind, funny_vote_counts=vote_counts)[:limit]

    def get(self, submission_id: str) -> SubmissionRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                select submission_id, season_id, puzzle_date, pair_id, ref_version, user_id, display_name,
                       image_hash, image_ref, friend_code, stroke_count, score, percentile, raw, bucket, ocr_cheat,
                       moderation, model_version, created_at, stroke_log_json
                from submissions
                where submission_id = ?
                """,
                (submission_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown submission_id: {submission_id}")
        return record_from_row(row)

    def count_user_submissions(self, puzzle_date: date, season_id: str, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                select count(*) as count
                from submissions
                where puzzle_date = ? and season_id = ? and user_id = ?
                """,
                (puzzle_date.isoformat(), normalize_season_id(season_id) or DEFAULT_SEASON_ID, user_id),
            ).fetchone()
        return int(row["count"])

    def rank_for(
        self,
        puzzle_date: date,
        submission_id: str,
        season_id: str = DEFAULT_SEASON_ID,
        kind: LeaderboardKind = "score",
        friend_code: str = "",
    ) -> int | None:
        for entry in self.leaderboard(
            puzzle_date,
            season_id=season_id,
            limit=10000,
            kind=kind,
            friend_code=friend_code,
        ):
            if entry.submission_id == submission_id:
                return entry.rank
        return None

    def record_funny_vote(
        self,
        submission_id: str,
        voter_user_id: str,
        created_at: datetime | None = None,
    ) -> tuple[bool, int]:
        if created_at is None:
            created_at = datetime.utcnow()
        with self._connect() as conn:
            submission = conn.execute(
                "select user_id from submissions where submission_id = ?",
                (submission_id,),
            ).fetchone()
            if submission is None:
                raise KeyError(f"Unknown submission_id: {submission_id}")
            cursor = conn.execute(
                """
                insert or ignore into funny_votes (submission_id, voter_user_id, created_at)
                values (?, ?, ?)
                """,
                (submission_id, voter_user_id, created_at.isoformat()),
            )
            count = conn.execute(
                "select count(*) as count from funny_votes where submission_id = ?",
                (submission_id,),
            ).fetchone()
        return cursor.rowcount > 0, int(count["count"])

    def funny_vote_count(self, submission_id: str) -> int:
        with self._connect() as conn:
            count = conn.execute(
                "select count(*) as count from funny_votes where submission_id = ?",
                (submission_id,),
            ).fetchone()
        return int(count["count"])

    def consume_rate_limit(
        self,
        actor_id: str,
        action: str,
        limit: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> RateLimitDecision:
        if now is None:
            now = datetime.now(timezone.utc)
        now_seconds = now.timestamp()
        cutoff_seconds = now_seconds - window_seconds
        with self._connect() as conn:
            conn.execute(
                "delete from rate_limit_events where occurred_at < ?",
                (cutoff_seconds,),
            )
            count_row = conn.execute(
                """
                select count(*) as count, min(occurred_at) as oldest
                from rate_limit_events
                where actor_id = ? and action = ? and occurred_at >= ?
                """,
                (actor_id, action, cutoff_seconds),
            ).fetchone()
            used = int(count_row["count"])
            if used >= limit:
                oldest = float(count_row["oldest"])
                retry_after = max(1, int((oldest + window_seconds) - now_seconds))
                return RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=retry_after)
            conn.execute(
                """
                insert into rate_limit_events (actor_id, action, occurred_at)
                values (?, ?, ?)
                """,
                (actor_id, action, now_seconds),
            )
        return RateLimitDecision(allowed=True, remaining=max(0, limit - used - 1))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("delete from submissions")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists submissions (
                    submission_id text primary key,
                    season_id text not null default 'season-1',
                    puzzle_date text not null,
                    pair_id text not null,
                    ref_version text not null,
                    user_id text not null,
                    display_name text not null,
                    image_hash text not null,
                    image_ref text not null default '',
                    friend_code text not null default '',
                    stroke_count integer not null,
                    score integer not null,
                    percentile real not null,
                    raw real not null,
                    bucket text not null,
                    ocr_cheat integer not null,
                    moderation text not null,
                    model_version text not null,
                    created_at text not null,
                    stroke_log_json text not null default ''
                )
                """
            )
            columns = {str(row["name"]) for row in conn.execute("pragma table_info(submissions)").fetchall()}
            if "season_id" not in columns:
                conn.execute("alter table submissions add column season_id text not null default 'season-1'")
            if "image_ref" not in columns:
                conn.execute("alter table submissions add column image_ref text not null default ''")
            if "friend_code" not in columns:
                conn.execute("alter table submissions add column friend_code text not null default ''")
            if "stroke_log_json" not in columns:
                conn.execute("alter table submissions add column stroke_log_json text not null default ''")
            conn.execute(
                "create index if not exists idx_submissions_daily_rank on submissions (season_id, puzzle_date, score desc, percentile desc, stroke_count asc, created_at asc)"
            )
            conn.execute(
                "create index if not exists idx_submissions_friend_rank on submissions (season_id, puzzle_date, friend_code, score desc, percentile desc, stroke_count asc, created_at asc)"
            )
            conn.execute(
                """
                create table if not exists funny_votes (
                    submission_id text not null,
                    voter_user_id text not null,
                    created_at text not null,
                    primary key (submission_id, voter_user_id)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_funny_votes_submission on funny_votes (submission_id)"
            )
            conn.execute(
                """
                create table if not exists rate_limit_events (
                    actor_id text not null,
                    action text not null,
                    occurred_at real not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_rate_limit_events_actor_action on rate_limit_events (actor_id, action, occurred_at)"
            )

    def _funny_vote_counts(self, submission_ids: list[str]) -> dict[str, int]:
        if not submission_ids:
            return {}
        placeholders = ",".join("?" for _ in submission_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select submission_id, count(*) as count
                from funny_votes
                where submission_id in ({placeholders})
                group by submission_id
                """,
                submission_ids,
            ).fetchall()
        return {str(row["submission_id"]): int(row["count"]) for row in rows}


class JsonSeedGhostRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def all(self) -> list[SubmissionRecord]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        return [record_from_payload(item) for item in payload.get("seed_ghosts", ())]


def record_from_row(row: sqlite3.Row) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=str(row["submission_id"]),
        season_id=str(row["season_id"]),
        puzzle_date=date.fromisoformat(str(row["puzzle_date"])),
        pair_id=str(row["pair_id"]),
        ref_version=str(row["ref_version"]),
        player=PlayerIdentity(
            user_id=str(row["user_id"]),
            display_name=str(row["display_name"]),
        ),
        image_hash=str(row["image_hash"]),
        image_ref=str(row["image_ref"]),
        friend_code=str(row["friend_code"]),
        stroke_count=int(row["stroke_count"]),
        score=int(row["score"]),
        percentile=float(row["percentile"]),
        raw=float(row["raw"]),
        bucket=str(row["bucket"]),
        ocr_cheat=bool(row["ocr_cheat"]),
        moderation=str(row["moderation"]),
        model_version=str(row["model_version"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        stroke_log=decode_stroke_log(str(row["stroke_log_json"])),
    )


def record_from_payload(payload: dict) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=str(payload["submission_id"]),
        season_id=normalize_season_id(str(payload.get("season_id", DEFAULT_SEASON_ID))) or DEFAULT_SEASON_ID,
        puzzle_date=date.fromisoformat(str(payload["puzzle_date"])),
        pair_id=str(payload["pair_id"]),
        ref_version=str(payload["ref_version"]),
        player=PlayerIdentity(
            user_id=str(payload["user_id"]),
            display_name=str(payload["display_name"]),
        ),
        image_hash=str(payload["image_hash"]),
        image_ref=str(payload.get("image_ref", "")),
        friend_code=normalize_friend_code(str(payload.get("friend_code", ""))),
        stroke_count=int(payload["stroke_count"]),
        score=int(payload["score"]),
        percentile=float(payload["percentile"]),
        raw=float(payload["raw"]),
        bucket=str(payload["bucket"]),
        ocr_cheat=bool(payload["ocr_cheat"]),
        moderation=str(payload["moderation"]),
        model_version=str(payload["model_version"]),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        stroke_log=stroke_log_from_payload(payload),
    )


def encode_stroke_log(stroke_log: dict | None) -> str:
    if not isinstance(stroke_log, dict):
        return ""
    return json.dumps(stroke_log, sort_keys=True, separators=(",", ":"))


def decode_stroke_log(value: str) -> dict | None:
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def stroke_log_from_payload(payload: dict) -> dict | None:
    stroke_log = payload.get("stroke_log")
    if isinstance(stroke_log, dict):
        return stroke_log
    return decode_stroke_log(str(payload.get("stroke_log_json", "")))
