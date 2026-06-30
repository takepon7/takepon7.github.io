from __future__ import annotations

from datetime import date
from pathlib import Path

from tools.plan_daily_puzzles_from_seed_scores import plan_daily_puzzles


def write_fixture_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    daily_path = tmp_path / "daily_puzzles.json"
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    daily_path.write_text(
        """
        {
          "daily_puzzles": [
            {
              "date": "2026-07-05",
              "pair_id": "apple_to_baseball",
              "ref_version": "phase0-heuristic-tau30-2026-06-29",
              "frozen_at": "2026-06-29T00:00:00+00:00"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    pairs_path.write_text(
        """
        {
          "pairs": [
            {
              "pair_id": "apple_to_baseball",
              "base": {"object_id": "apple", "canonical_label": "apple", "aliases": ["apples"]},
              "target": {"object_id": "baseball", "canonical_label": "baseball", "aliases": ["base ball"]},
              "hard_negatives": [
                {"object_id": "tennis_ball", "canonical_label": "tennis ball", "aliases": ["tennisball"]},
                {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]},
                {"object_id": "orange", "canonical_label": "orange", "aliases": []}
              ]
            },
            {
              "pair_id": "orange_to_tennis_ball",
              "base": {"object_id": "orange", "canonical_label": "orange", "aliases": []},
              "target": {"object_id": "tennis_ball", "canonical_label": "tennis ball", "aliases": ["tennisball"]},
              "hard_negatives": [
                {"object_id": "baseball", "canonical_label": "baseball", "aliases": ["base ball"]},
                {"object_id": "apple", "canonical_label": "apple", "aliases": ["apples"]},
                {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]}
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    seed_scores_path.write_text(
        """
        {
          "seed_scores": [
            {
              "ref_version": "approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30",
              "pair_id": "apple_to_baseball",
              "model_version": "heuristic-color-shape-v1",
              "template_set_id": "drawing_v1",
              "tau": 30.0,
              "scores_sorted": [0.0, 0.5, 1.0],
              "stats": {"min": 0.0, "p10": 0.1, "p50": 0.5, "p90": 0.9, "max": 1.0, "mean": 0.5, "std": 0.4}
            },
            {
              "ref_version": "approved-seed-heuristic-color-shape-v1-orange-tennis-ball-tau30-2026-06-30",
              "pair_id": "orange_to_tennis_ball",
              "model_version": "heuristic-color-shape-v1",
              "template_set_id": "drawing_v1",
              "tau": 30.0,
              "scores_sorted": [0.1, 0.55, 0.95],
              "stats": {"min": 0.1, "p10": 0.19, "p50": 0.55, "p90": 0.87, "max": 0.95, "mean": 0.5333333333, "std": 0.35}
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    return daily_path, pairs_path, seed_scores_path


def test_daily_puzzle_plan_schedules_accepted_unscheduled_pair(tmp_path: Path) -> None:
    daily_path, pairs_path, seed_scores_path = write_fixture_files(tmp_path)

    report = plan_daily_puzzles(
        daily_puzzles_path=daily_path,
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=tmp_path / "plan",
        days=2,
    )

    assert report["errors"] == []
    assert len(report["planned"]) == 1
    assert report["planned"][0]["date"] == "2026-07-06"
    assert report["planned"][0]["pair_id"] == "orange_to_tennis_ball"
    assert report["skipped"][0]["reason"] == "pair_already_scheduled"
    assert "orange_to_tennis_ball" in (tmp_path / "plan" / "merged_daily_puzzles.json").read_text(encoding="utf-8")
    assert "orange_to_tennis_ball" not in daily_path.read_text(encoding="utf-8")


def test_daily_puzzle_plan_can_allow_repeat_pairs(tmp_path: Path) -> None:
    daily_path, pairs_path, seed_scores_path = write_fixture_files(tmp_path)

    report = plan_daily_puzzles(
        daily_puzzles_path=daily_path,
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=tmp_path / "plan",
        days=2,
        allow_repeat_pairs=True,
    )

    assert report["errors"] == []
    assert [item["pair_id"] for item in report["planned"]] == [
        "apple_to_baseball",
        "orange_to_tennis_ball",
    ]


def test_daily_puzzle_plan_reports_date_conflicts(tmp_path: Path) -> None:
    daily_path, pairs_path, seed_scores_path = write_fixture_files(tmp_path)

    report = plan_daily_puzzles(
        daily_puzzles_path=daily_path,
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=tmp_path / "plan",
        start_date=date(2026, 7, 5),
        days=1,
    )

    assert report["applied"] is False
    assert report["errors"][0]["kind"] == "date_conflict"
