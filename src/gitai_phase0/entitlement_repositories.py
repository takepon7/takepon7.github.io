from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from gitai_phase0.entitlements import (
    PremiumEntitlement,
    PremiumRedeemResult,
    entitlement_is_active,
    normalize_redeem_code,
)


class SqliteEntitlementRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init_schema()

    def has_premium_access(self, user_id: str) -> bool:
        now = datetime.now(timezone.utc)
        entitlement = self.active_entitlement(user_id, now=now)
        return entitlement is not None

    def active_entitlement(self, user_id: str, now: datetime | None = None) -> PremiumEntitlement | None:
        if now is None:
            now = datetime.now(timezone.utc)
        with self._connect() as conn:
            row = conn.execute(
                """
                select user_id, source, granted_at, expires_at
                from premium_entitlements
                where user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        entitlement = entitlement_from_row(row)
        if not entitlement_is_active(entitlement, now):
            return None
        return entitlement

    def grant_premium(
        self,
        user_id: str,
        source: str,
        granted_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> PremiumEntitlement:
        if granted_at is None:
            granted_at = datetime.now(timezone.utc)
        entitlement = PremiumEntitlement(
            user_id=user_id,
            source=source,
            granted_at=granted_at,
            expires_at=expires_at,
        )
        with self._connect() as conn:
            upsert_entitlement(conn, entitlement)
        return entitlement

    def seed_redeem_code(
        self,
        code: str,
        max_redemptions: int = 100,
        expires_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> str:
        normalized = normalize_redeem_code(code)
        if not normalized:
            raise ValueError("premium redeem code must not be blank")
        if created_at is None:
            created_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                insert into premium_redeem_codes (
                    code, max_redemptions, expires_at, created_at
                ) values (?, ?, ?, ?)
                on conflict(code) do update set
                    max_redemptions = excluded.max_redemptions,
                    expires_at = excluded.expires_at
                """,
                (
                    normalized,
                    max(1, int(max_redemptions)),
                    expires_at.isoformat() if expires_at else None,
                    created_at.isoformat(),
                ),
            )
        return normalized

    def redeem_premium_code(
        self,
        user_id: str,
        code: str,
        now: datetime | None = None,
    ) -> PremiumRedeemResult:
        if now is None:
            now = datetime.now(timezone.utc)
        normalized = normalize_redeem_code(code)
        if not user_id.strip() or not normalized:
            return PremiumRedeemResult(user_id=user_id, code=normalized, status="invalid", premium=False)

        with self._connect() as conn:
            code_row = conn.execute(
                """
                select code, max_redemptions, expires_at
                from premium_redeem_codes
                where code = ?
                """,
                (normalized,),
            ).fetchone()
            if code_row is None:
                return PremiumRedeemResult(user_id=user_id, code=normalized, status="invalid", premium=False)
            expires_at = parse_datetime_or_none(code_row["expires_at"])
            if expires_at is not None and expires_at <= now:
                return PremiumRedeemResult(user_id=user_id, code=normalized, status="expired", premium=False)
            already = conn.execute(
                """
                select 1
                from premium_redemptions
                where code = ? and user_id = ?
                """,
                (normalized, user_id),
            ).fetchone()
            if already is not None:
                return PremiumRedeemResult(
                    user_id=user_id,
                    code=normalized,
                    status="already_redeemed",
                    premium=entitlement_row_is_active(conn, user_id, now),
                )
            redemption_count = conn.execute(
                "select count(*) as count from premium_redemptions where code = ?",
                (normalized,),
            ).fetchone()
            if int(redemption_count["count"]) >= int(code_row["max_redemptions"]):
                return PremiumRedeemResult(user_id=user_id, code=normalized, status="exhausted", premium=False)

            conn.execute(
                """
                insert into premium_redemptions (code, user_id, redeemed_at)
                values (?, ?, ?)
                """,
                (normalized, user_id, now.isoformat()),
            )
            upsert_entitlement(
                conn,
                PremiumEntitlement(
                    user_id=user_id,
                    source=f"redeem:{normalized}",
                    granted_at=now,
                    expires_at=None,
                ),
            )
        return PremiumRedeemResult(user_id=user_id, code=normalized, status="redeemed", premium=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists premium_entitlements (
                    user_id text primary key,
                    source text not null,
                    granted_at text not null,
                    expires_at text
                )
                """
            )
            conn.execute(
                """
                create table if not exists premium_redeem_codes (
                    code text primary key,
                    max_redemptions integer not null,
                    expires_at text,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists premium_redemptions (
                    code text not null,
                    user_id text not null,
                    redeemed_at text not null,
                    primary key (code, user_id)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_premium_redemptions_user on premium_redemptions (user_id)"
            )


def upsert_entitlement(conn: sqlite3.Connection, entitlement: PremiumEntitlement) -> None:
    conn.execute(
        """
        insert into premium_entitlements (
            user_id, source, granted_at, expires_at
        ) values (?, ?, ?, ?)
        on conflict(user_id) do update set
            source = excluded.source,
            granted_at = excluded.granted_at,
            expires_at = excluded.expires_at
        """,
        (
            entitlement.user_id,
            entitlement.source,
            entitlement.granted_at.isoformat(),
            entitlement.expires_at.isoformat() if entitlement.expires_at else None,
        ),
    )


def entitlement_row_is_active(conn: sqlite3.Connection, user_id: str, now: datetime) -> bool:
    row = conn.execute(
        """
        select user_id, source, granted_at, expires_at
        from premium_entitlements
        where user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return False
    return entitlement_is_active(entitlement_from_row(row), now)


def entitlement_from_row(row: sqlite3.Row) -> PremiumEntitlement:
    return PremiumEntitlement(
        user_id=str(row["user_id"]),
        source=str(row["source"]),
        granted_at=datetime.fromisoformat(str(row["granted_at"])),
        expires_at=parse_datetime_or_none(row["expires_at"]),
    )


def parse_datetime_or_none(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))
