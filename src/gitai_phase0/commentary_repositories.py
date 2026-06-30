from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3

from gitai_phase0.commentary import AppraisalComment


class SqliteAppraisalRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init_schema()

    def get_cached_comment(self, submission_id: str) -> AppraisalComment | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select line, mood, source, template_id
                from appraisal_comment_cache
                where submission_id = ?
                """,
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return AppraisalComment(
            line=str(row["line"]),
            mood=str(row["mood"]),
            source=str(row["source"]),
            template_id=str(row["template_id"]),
        )

    def cache_comment(
        self,
        submission_id: str,
        user_id: str,
        comment: AppraisalComment,
        actor_version: str,
        cost_units: int,
        day: date,
        created_at: datetime | None = None,
    ) -> bool:
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert or ignore into appraisal_comment_cache (
                    submission_id, line, mood, source, template_id,
                    actor_version, cost_units, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    comment.line,
                    comment.mood,
                    comment.source,
                    comment.template_id,
                    actor_version,
                    cost_units,
                    created_at.isoformat(),
                ),
            )
            inserted = cursor.rowcount > 0
            if inserted and cost_units > 0:
                insert_spend_event(conn, day, submission_id, user_id, actor_version, cost_units, created_at)
        return inserted

    def record_spend(
        self,
        submission_id: str,
        user_id: str,
        actor_version: str,
        cost_units: int,
        day: date,
        created_at: datetime | None = None,
    ) -> None:
        if cost_units <= 0:
            return
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            insert_spend_event(conn, day, submission_id, user_id, actor_version, cost_units, created_at)

    def daily_spend(self, day: date) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "select coalesce(sum(cost_units), 0) as total from llm_spend_events where day = ?",
                (day.isoformat(),),
            ).fetchone()
        return int(row["total"])

    def user_daily_count(self, user_id: str, day: date) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                select count(*) as count
                from llm_spend_events
                where day = ? and user_id = ?
                """,
                (day.isoformat(), user_id),
            ).fetchone()
        return int(row["count"])

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists appraisal_comment_cache (
                    submission_id text primary key,
                    line text not null,
                    mood text not null,
                    source text not null,
                    template_id text not null,
                    actor_version text not null,
                    cost_units integer not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists llm_spend_events (
                    day text not null,
                    submission_id text not null,
                    user_id text not null,
                    actor_version text not null,
                    cost_units integer not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_llm_spend_events_day on llm_spend_events (day)"
            )
            conn.execute(
                "create index if not exists idx_llm_spend_events_user_day on llm_spend_events (user_id, day)"
            )


def insert_spend_event(
    conn: sqlite3.Connection,
    day: date,
    submission_id: str,
    user_id: str,
    actor_version: str,
    cost_units: int,
    created_at: datetime,
) -> None:
    conn.execute(
        """
        insert into llm_spend_events (
            day, submission_id, user_id, actor_version, cost_units, created_at
        ) values (?, ?, ?, ?, ?, ?)
        """,
        (day.isoformat(), submission_id, user_id, actor_version, cost_units, created_at.isoformat()),
    )
