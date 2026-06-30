from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from gitai_phase0.cosmetics import COSMETIC_CATALOG, CosmeticSpec, CosmeticUnlock, cosmetic_by_id

COSMETIC_ORDER = {spec.cosmetic_id: index for index, spec in enumerate(COSMETIC_CATALOG)}


class SqliteCosmeticRepository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init_schema()

    def unlocked_cosmetics(self, user_id: str, season_id: str) -> list[CosmeticUnlock]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select cosmetic_id, unlocked_at
                from cosmetic_unlocks
                where user_id = ? and season_id = ?
                order by unlocked_at, cosmetic_id
                """,
                (user_id, season_id),
            ).fetchall()
        unlocks: list[CosmeticUnlock] = []
        for row in rows:
            spec = cosmetic_by_id(str(row["cosmetic_id"]))
            if spec is None:
                continue
            unlocks.append(
                CosmeticUnlock(
                    user_id=user_id,
                    season_id=season_id,
                    cosmetic=spec,
                    unlocked_at=datetime.fromisoformat(str(row["unlocked_at"])),
                )
            )
        return sorted(unlocks, key=lambda item: COSMETIC_ORDER.get(item.cosmetic.cosmetic_id, 10_000))

    def unlock_cosmetics(
        self,
        user_id: str,
        season_id: str,
        cosmetics: tuple[CosmeticSpec, ...],
        unlocked_at: datetime | None = None,
    ) -> list[CosmeticUnlock]:
        if unlocked_at is None:
            unlocked_at = datetime.now(timezone.utc)
        unlocked: list[CosmeticUnlock] = []
        with self._connect() as conn:
            for cosmetic in cosmetics:
                cursor = conn.execute(
                    """
                    insert or ignore into cosmetic_unlocks (
                        user_id, season_id, cosmetic_id, unlocked_at
                    ) values (?, ?, ?, ?)
                    """,
                    (user_id, season_id, cosmetic.cosmetic_id, unlocked_at.isoformat()),
                )
                if cursor.rowcount > 0:
                    unlocked.append(
                        CosmeticUnlock(
                            user_id=user_id,
                            season_id=season_id,
                            cosmetic=cosmetic,
                            unlocked_at=unlocked_at,
                            newly_unlocked=True,
                        )
                    )
        return unlocked

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists cosmetic_unlocks (
                    user_id text not null,
                    season_id text not null,
                    cosmetic_id text not null,
                    unlocked_at text not null,
                    primary key (user_id, season_id, cosmetic_id)
                )
                """
            )
            conn.execute(
                "create index if not exists idx_cosmetic_unlocks_user_season on cosmetic_unlocks (user_id, season_id)"
            )
