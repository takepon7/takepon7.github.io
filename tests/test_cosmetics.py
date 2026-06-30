from __future__ import annotations

from datetime import datetime, timezone

from gitai_phase0.cosmetic_repositories import SqliteCosmeticRepository
from gitai_phase0.cosmetics import COSMETIC_CATALOG, rewardable_cosmetics_for_submission
from gitai_phase0.competition import PlayerIdentity, SubmissionRecord


def test_cosmetic_unlocks_are_unique_per_user_and_season(tmp_path) -> None:
    repo = SqliteCosmeticRepository(tmp_path / "cosmetics.sqlite")
    rewards = tuple(spec for spec in COSMETIC_CATALOG if spec.score_floor > 0)

    first = repo.unlock_cosmetics("player", "season-1", rewards)
    duplicate = repo.unlock_cosmetics("player", "season-1", rewards)
    next_season = repo.unlock_cosmetics("player", "season-2", rewards[:1])

    assert [item.cosmetic.cosmetic_id for item in first] == ["palette-verdict", "palette-masterpiece"]
    assert duplicate == []
    assert [item.cosmetic.cosmetic_id for item in next_season] == ["palette-verdict"]
    assert [item.cosmetic.cosmetic_id for item in repo.unlocked_cosmetics("player", "season-1")] == [
        "palette-verdict",
        "palette-masterpiece",
    ]


def test_rewardable_cosmetics_ignore_unsafe_submission() -> None:
    assert rewardable_cosmetics_for_submission(record(score=1000, ocr_cheat=True)) == ()
    assert rewardable_cosmetics_for_submission(record(score=1000, moderation="flag")) == ()
    assert [item.cosmetic_id for item in rewardable_cosmetics_for_submission(record(score=700))] == [
        "palette-verdict"
    ]


def record(score: int, ocr_cheat: bool = False, moderation: str = "pass") -> SubmissionRecord:
    return SubmissionRecord(
        submission_id="cosmetic-test",
        season_id="season-1",
        puzzle_date=datetime(2026, 6, 29, tzinfo=timezone.utc).date(),
        pair_id="apple_to_baseball",
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity("player", "player"),
        image_hash="hash",
        stroke_count=1,
        score=score,
        percentile=score / 1000,
        raw=score / 1000,
        bucket="fooled",
        ocr_cheat=ocr_cheat,
        moderation=moderation,
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )
