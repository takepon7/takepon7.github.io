from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

from PIL import Image

from gitai_phase0.competition import PlayerIdentity, SubmissionRecord
from gitai_phase0.competition_repositories import JsonSeedGhostRepository, SqliteSubmissionRepository
from gitai_phase0.drawing_verification import CanvasStrokeReplayVerifier, parse_stroke_log
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository
from tools.build_seed_ghost_pack import build_seed_ghost_pack
from tools.validate_phase4_seed_ghosts import build_report


def test_seed_ghosts_bootstrap_leaderboard_without_duplicates(tmp_path: Path) -> None:
    ghosts = JsonSeedGhostRepository(Path("data/competition/seed_ghosts.json")).all()
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")

    repo.seed(ghosts)
    repo.seed(ghosts)

    entries = repo.leaderboard(date(2026, 6, 29))
    assert [entry.submission_id for entry in entries] == [
        "seed-2026-06-29-apple_to_baseball-score",
        "seed-2026-06-29-apple_to_baseball-fast",
    ]
    assert entries[0].score == 960
    assert entries[1].score == 760
    assert entries[0].image_ref == "file:data/competition/seed_ghost_images/seed-2026-06-29-apple_to_baseball-score.png"

    efficiency = repo.leaderboard(date(2026, 6, 29), kind="efficiency")
    assert [entry.submission_id for entry in efficiency] == [
        "seed-2026-06-29-apple_to_baseball-fast",
        "seed-2026-06-29-apple_to_baseball-score",
    ]


def test_seed_ghosts_cover_each_playtest_daily_puzzle(tmp_path: Path) -> None:
    ghosts = JsonSeedGhostRepository(Path("data/competition/seed_ghosts.json")).all()
    daily = DailyPuzzleRepository(Path("data/puzzle/daily_puzzles.json")).list()
    pairs = PairRepository(Path("data/scoring/pairs.json"))
    verifier = CanvasStrokeReplayVerifier()
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.seed(ghosts)

    assert len(ghosts) == len(daily) * 2
    for puzzle in daily:
        records = [record for record in ghosts if record.puzzle_date == puzzle.date]
        assert len(records) == 2
        assert {record.pair_id for record in records} == {puzzle.pair_id}
        assert {record.ref_version for record in records} == {puzzle.ref_version}
        for record in records:
            assert record.model_version == "heuristic-color-shape-v1"
            assert record.bucket == "fooled"
            assert record.moderation == "pass"
            assert record.image_ref.startswith("file:")
            image_path = Path(record.image_ref.removeprefix("file:"))
            assert image_path.exists()
            strokes = parse_stroke_log(record.stroke_log, max_strokes=250, max_points_per_stroke=2000)
            assert strokes is not None
            assert len(strokes) == record.stroke_count
            with Image.open(image_path) as image:
                assert verifier.verify(image.convert("RGBA"), pairs.get(record.pair_id), record.stroke_log).accepted

        score_entries = repo.leaderboard(puzzle.date, kind="score")
        efficiency_entries = repo.leaderboard(puzzle.date, kind="efficiency")
        assert score_entries[0].score == 960
        assert efficiency_entries[0].stroke_count == 2


def test_seed_ghost_pack_can_build_from_planned_daily_preview(tmp_path: Path) -> None:
    daily_path = tmp_path / "daily_puzzles.json"
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    seed_ghosts_path = tmp_path / "seed_ghosts.json"
    out_dir = tmp_path / "seed_ghost_images"
    ref_version = "approved-seed-heuristic-color-shape-v1-orange-tennis-ball-tau30-2026-06-30"

    daily_path.write_text(
        json.dumps(
            {
                "daily_puzzles": [
                    {
                        "date": "2026-07-06",
                        "pair_id": "orange_to_tennis_ball",
                        "ref_version": ref_version,
                        "frozen_at": "2026-06-30T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    pairs_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair_id": "orange_to_tennis_ball",
                        "base": {"object_id": "orange", "canonical_label": "orange", "aliases": []},
                        "target": {
                            "object_id": "tennis_ball",
                            "canonical_label": "tennis ball",
                            "aliases": ["tennisball"],
                        },
                        "hard_negatives": [
                            {
                                "object_id": "baseball",
                                "canonical_label": "baseball",
                                "aliases": ["base ball"],
                            },
                            {"object_id": "apple", "canonical_label": "apple", "aliases": ["apples"]},
                            {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    seed_scores_path.write_text(
        json.dumps(
            {
                "seed_scores": [
                    {
                        "ref_version": ref_version,
                        "pair_id": "orange_to_tennis_ball",
                        "model_version": "heuristic-color-shape-v1",
                        "template_set_id": "drawing_v1",
                        "tau": 30.0,
                        "scores_sorted": [0.1, 0.55, 0.95],
                        "stats": {
                            "min": 0.1,
                            "p10": 0.19,
                            "p50": 0.55,
                            "p90": 0.87,
                            "max": 0.95,
                            "mean": 0.5333333333,
                            "std": 0.35,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    ghosts = build_seed_ghost_pack(
        daily_puzzles_path=daily_path,
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=out_dir,
        season_id="season-test",
    )
    seed_ghosts_path.write_text(json.dumps({"seed_ghosts": ghosts}), encoding="utf-8")
    report = build_report(
        daily_puzzles_path=daily_path,
        pairs_path=pairs_path,
        seed_ghosts_path=seed_ghosts_path,
        season_id="season-test",
    )

    assert len(ghosts) == 2
    assert {ghost["display_name"] for ghost in ghosts} == {"Seed Ghost", "Fast Ghost"}
    assert {len(ghost["stroke_log"]["strokes"]) for ghost in ghosts} == {2, 8}
    assert all(Path(ghost["image_ref"].removeprefix("file:")).exists() for ghost in ghosts)
    assert report.valid is True
    assert report.rows[0].seed_count == 2
    assert report.rows[0].replayable_stroke_logs is True


def test_efficiency_leaderboard_keeps_score_separate(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("high-score", score=1000, bucket="fooled", strokes=9, created_second=1))
    repo.save(record("efficient", score=920, bucket="fooled", strokes=3, created_second=2))
    repo.save(record("failed-fast", score=990, bucket="failed", strokes=1, created_second=3))

    score_entries = repo.leaderboard(date(2026, 6, 29), kind="score")
    efficiency_entries = repo.leaderboard(date(2026, 6, 29), kind="efficiency")

    assert [entry.submission_id for entry in score_entries] == ["high-score", "failed-fast", "efficient"]
    assert [entry.submission_id for entry in efficiency_entries] == ["efficient", "high-score"]


def test_friend_leaderboard_filters_by_code(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("room-a-high", score=1000, bucket="fooled", strokes=6, created_second=1, friend_code="room-a"))
    repo.save(record("room-b-high", score=990, bucket="fooled", strokes=1, created_second=2, friend_code="room-b"))
    repo.save(record("room-a-low", score=500, bucket="failed", strokes=2, created_second=3, friend_code="ROOM-A"))

    entries = repo.leaderboard(date(2026, 6, 29), kind="friend", friend_code="Room-A")

    assert [entry.submission_id for entry in entries] == ["room-a-high", "room-a-low"]
    assert [entry.friend_code for entry in entries] == ["ROOM-A", "ROOM-A"]
    assert repo.rank_for(date(2026, 6, 29), "room-a-low", kind="friend", friend_code="room-a") == 2


def test_funny_leaderboard_uses_unique_votes(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("funniest", score=500, bucket="failed", strokes=6, created_second=1))
    repo.save(record("stronger", score=1000, bucket="fooled", strokes=3, created_second=2))
    repo.save(record("unvoted", score=999, bucket="fooled", strokes=2, created_second=3))

    assert repo.record_funny_vote("funniest", "voter-1") == (True, 1)
    assert repo.record_funny_vote("funniest", "voter-1") == (False, 1)
    assert repo.record_funny_vote("funniest", "voter-2") == (True, 2)
    assert repo.record_funny_vote("stronger", "voter-3") == (True, 1)

    entries = repo.leaderboard(date(2026, 6, 29), kind="funny")

    assert [entry.submission_id for entry in entries] == ["funniest", "stronger"]
    assert [entry.funny_votes for entry in entries] == [2, 1]


def test_public_leaderboards_exclude_cheats_and_flagged_records(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("visible", score=700, bucket="failed", strokes=5, created_second=1))
    repo.save(record("text-cheat", score=1000, bucket="fooled", strokes=1, created_second=2, ocr_cheat=True))
    repo.save(record("flagged", score=999, bucket="fooled", strokes=1, created_second=3, moderation="flag"))
    repo.record_funny_vote("text-cheat", "viewer")
    repo.record_funny_vote("flagged", "viewer")
    repo.record_funny_vote("visible", "viewer")

    score_entries = repo.leaderboard(date(2026, 6, 29), kind="score")
    funny_entries = repo.leaderboard(date(2026, 6, 29), kind="funny")

    assert [entry.submission_id for entry in score_entries] == ["visible"]
    assert [entry.submission_id for entry in funny_entries] == ["visible"]


def test_rate_limit_uses_fixed_window(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    now = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)

    first = repo.consume_rate_limit("player", "submit", limit=2, window_seconds=60, now=now)
    second = repo.consume_rate_limit("player", "submit", limit=2, window_seconds=60, now=now + timedelta(seconds=1))
    blocked = repo.consume_rate_limit("player", "submit", limit=2, window_seconds=60, now=now + timedelta(seconds=2))
    reopened = repo.consume_rate_limit("player", "submit", limit=2, window_seconds=60, now=now + timedelta(seconds=61))

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 58
    assert reopened.allowed is True
    assert reopened.remaining == 0


def test_counts_user_submissions_by_day(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("player-a-1", score=800, bucket="fooled", strokes=4, created_second=1, user_id="player-a"))
    repo.save(record("player-a-2", score=700, bucket="failed", strokes=4, created_second=2, user_id="player-a"))
    repo.save(record("player-b-1", score=900, bucket="fooled", strokes=4, created_second=3, user_id="player-b"))

    assert repo.count_user_submissions(date(2026, 6, 29), "season-1", "player-a") == 2
    assert repo.count_user_submissions(date(2026, 6, 29), "season-1", "player-b") == 1
    assert repo.count_user_submissions(date(2026, 6, 30), "season-1", "player-a") == 0


def test_leaderboard_is_scoped_by_season(tmp_path: Path) -> None:
    repo = SqliteSubmissionRepository(tmp_path / "submissions.sqlite")
    repo.save(record("season-one-top", score=1000, bucket="fooled", strokes=4, created_second=1, season_id="season-1"))
    repo.save(record("season-two-top", score=999, bucket="fooled", strokes=4, created_second=2, season_id="season-2"))

    season_one = repo.leaderboard(date(2026, 6, 29), season_id="season-1")
    season_two = repo.leaderboard(date(2026, 6, 29), season_id="season-2")

    assert [entry.submission_id for entry in season_one] == ["season-one-top"]
    assert [entry.submission_id for entry in season_two] == ["season-two-top"]
    assert repo.rank_for(date(2026, 6, 29), "season-two-top", season_id="season-1") is None
    assert repo.rank_for(date(2026, 6, 29), "season-two-top", season_id="season-2") == 1


def record(
    submission_id: str,
    score: int,
    bucket: str,
    strokes: int,
    created_second: int,
    friend_code: str = "",
    ocr_cheat: bool = False,
    moderation: str = "pass",
    user_id: str | None = None,
    season_id: str = "season-1",
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=submission_id,
        puzzle_date=date(2026, 6, 29),
        pair_id="apple_to_baseball",
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity(user_id=user_id or submission_id, display_name=submission_id),
        image_hash=submission_id,
        image_ref=f"memory:{submission_id}",
        stroke_count=strokes,
        score=score,
        percentile=score / 1000,
        raw=score / 1000,
        bucket=bucket,
        ocr_cheat=ocr_cheat,
        moderation=moderation,
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, 0, 0, created_second, tzinfo=timezone.utc),
        season_id=season_id,
        friend_code=friend_code.upper(),
    )
