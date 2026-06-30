from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from collections.abc import Mapping
from typing import Literal

LeaderboardKind = Literal["score", "efficiency", "friend", "funny"]
DEFAULT_SEASON_ID = "season-1"


@dataclass(frozen=True)
class SeasonSpec:
    season_id: str
    label: str
    model_version: str

    def __post_init__(self) -> None:
        if not normalize_season_id(self.season_id):
            raise ValueError("season_id must not be blank.")
        if not self.label.strip():
            raise ValueError("season label must not be blank.")
        if not self.model_version.strip():
            raise ValueError("season model_version must not be blank.")


@dataclass(frozen=True)
class PlayerIdentity:
    user_id: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id must not be blank.")
        if not self.display_name.strip():
            raise ValueError("display_name must not be blank.")


@dataclass(frozen=True)
class SubmissionRecord:
    submission_id: str
    puzzle_date: date
    pair_id: str
    ref_version: str
    player: PlayerIdentity
    image_hash: str
    stroke_count: int
    score: int
    percentile: float
    raw: float
    bucket: str
    ocr_cheat: bool
    moderation: str
    model_version: str
    created_at: datetime
    season_id: str = DEFAULT_SEASON_ID
    image_ref: str = ""
    friend_code: str = ""
    stroke_log: dict | None = None


@dataclass(frozen=True)
class LeaderboardEntry:
    rank: int
    submission_id: str
    user_id: str
    display_name: str
    score: int
    percentile: float
    raw: float
    bucket: str
    stroke_count: int
    created_at: datetime
    season_id: str = DEFAULT_SEASON_ID
    image_ref: str = ""
    friend_code: str = ""
    funny_votes: int = 0


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int = 0


def rank_records(
    records: list[SubmissionRecord],
    kind: LeaderboardKind = "score",
    funny_vote_counts: Mapping[str, int] | None = None,
) -> list[LeaderboardEntry]:
    rankable_records = [record for record in records if is_publicly_rankable(record)]
    vote_counts = funny_vote_counts or {}
    if kind == "efficiency":
        ranked = sorted(
            [record for record in rankable_records if is_efficiency_qualified(record)],
            key=lambda item: (item.stroke_count, -item.score, -item.percentile, item.created_at, item.submission_id),
        )
    elif kind == "funny":
        ranked = sorted(
            [record for record in rankable_records if vote_counts.get(record.submission_id, 0) > 0],
            key=lambda item: (
                -vote_counts.get(item.submission_id, 0),
                -item.score,
                -item.percentile,
                item.stroke_count,
                item.created_at,
                item.submission_id,
            ),
        )
    else:
        ranked = sorted(
            rankable_records,
            key=lambda item: (-item.score, -item.percentile, item.stroke_count, item.created_at, item.submission_id),
        )
    return [
        LeaderboardEntry(
            rank=index + 1,
            submission_id=record.submission_id,
            user_id=record.player.user_id,
            display_name=record.player.display_name,
            score=record.score,
            percentile=record.percentile,
            raw=record.raw,
            bucket=record.bucket,
            stroke_count=record.stroke_count,
            created_at=record.created_at,
            season_id=record.season_id,
            image_ref=record.image_ref,
            friend_code=record.friend_code,
            funny_votes=vote_counts.get(record.submission_id, 0),
        )
        for index, record in enumerate(ranked)
    ]


def is_efficiency_qualified(record: SubmissionRecord) -> bool:
    return record.bucket == "fooled" and not record.ocr_cheat and record.moderation == "pass"


def is_publicly_rankable(record: SubmissionRecord) -> bool:
    return not record.ocr_cheat and record.moderation == "pass"


def count_strokes(stroke_log) -> int:
    if not isinstance(stroke_log, dict):
        return 0
    strokes = stroke_log.get("strokes")
    if not isinstance(strokes, list):
        return 0
    return len(strokes)


def normalize_friend_code(value: str) -> str:
    cleaned = "".join(
        char.upper()
        for char in value.strip()
        if char.isascii() and (char.isalnum() or char == "-")
    )
    compacted = "-".join(part for part in cleaned.split("-") if part)
    return compacted[:16]


def normalize_season_id(value: str) -> str:
    cleaned = "".join(
        char.lower()
        for char in value.strip()
        if char.isascii() and (char.isalnum() or char in "-_")
    )
    return cleaned[:48]
