from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from gitai_phase0.competition import SubmissionRecord

CosmeticKind = Literal["palette"]


@dataclass(frozen=True)
class CosmeticSpec:
    cosmetic_id: str
    kind: CosmeticKind
    label: str
    colors: tuple[str, ...]
    score_floor: int


@dataclass(frozen=True)
class CosmeticUnlock:
    user_id: str
    season_id: str
    cosmetic: CosmeticSpec
    unlocked_at: datetime
    newly_unlocked: bool = False


COSMETIC_CATALOG: tuple[CosmeticSpec, ...] = (
    CosmeticSpec(
        cosmetic_id="palette-classic",
        kind="palette",
        label="Classic",
        colors=("#1f1d1a", "#e9e5d8", "#d6453d", "#2f875a", "#e7c24e", "#315f9d"),
        score_floor=0,
    ),
    CosmeticSpec(
        cosmetic_id="palette-verdict",
        kind="palette",
        label="Verdict",
        colors=("#22201d", "#fffdf7", "#1f5f4a", "#8b4538", "#2a9876", "#d7472f"),
        score_floor=700,
    ),
    CosmeticSpec(
        cosmetic_id="palette-masterpiece",
        kind="palette",
        label="Masterpiece",
        colors=("#181716", "#ffffff", "#244f43", "#b33b2e", "#d7a62f", "#315f9d"),
        score_floor=950,
    ),
)


def default_cosmetics(user_id: str, season_id: str, unlocked_at: datetime) -> tuple[CosmeticUnlock, ...]:
    return tuple(
        CosmeticUnlock(
            user_id=user_id,
            season_id=season_id,
            cosmetic=spec,
            unlocked_at=unlocked_at,
            newly_unlocked=False,
        )
        for spec in COSMETIC_CATALOG
        if spec.score_floor == 0
    )


def cosmetic_by_id(cosmetic_id: str) -> CosmeticSpec | None:
    for spec in COSMETIC_CATALOG:
        if spec.cosmetic_id == cosmetic_id:
            return spec
    return None


def rewardable_cosmetics_for_submission(submission: SubmissionRecord) -> tuple[CosmeticSpec, ...]:
    if submission.ocr_cheat or submission.moderation != "pass":
        return ()
    return tuple(
        spec
        for spec in COSMETIC_CATALOG
        if spec.score_floor > 0 and submission.score >= spec.score_floor
    )
