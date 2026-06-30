from __future__ import annotations

import json
from pathlib import Path

from tools.apply_release_candidate import apply_release_candidate
from tools.build_seed_ghost_pack import build_seed_ghost_pack
from tools.rollback_release_candidate import rollback_release_candidate
from tools.validate_release_candidate import validate_release_candidate


def test_release_candidate_validation_accepts_planned_daily_with_seed_ghosts(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture(tmp_path)
    ghosts = build_seed_ghost_pack(
        daily_puzzles_path=paths["daily_puzzles"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        out_dir=tmp_path / "seed_ghost_images",
        season_id="season-test",
    )
    paths["seed_ghosts"].write_text(json.dumps({"seed_ghosts": ghosts}), encoding="utf-8")

    report = validate_release_candidate(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        out_dir=tmp_path / "release",
        season_id="season-test",
    )

    assert report["valid"] is True
    assert report["summary"]["planned_count"] == 1
    assert report["summary"]["seed_ghost_count"] == 2
    assert report["api_preview_env"]["GITAI_TODAY"] == "2026-07-06"
    assert (tmp_path / "release" / "release_candidate.json").exists()
    assert "promotion is a preview" in report["warnings"][0]


def test_release_candidate_validation_rejects_missing_seed_ghosts(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture(tmp_path)
    paths["seed_ghosts"].write_text(json.dumps({"seed_ghosts": []}), encoding="utf-8")

    report = validate_release_candidate(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        out_dir=tmp_path / "release",
        season_id="season-test",
    )

    assert report["valid"] is False
    assert any("seed_ghosts_cover_daily_entries" in error for error in report["errors"])


def test_apply_release_candidate_dry_run_leaves_canonical_files_untouched(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture_with_ghosts(tmp_path)
    canonical_pairs = tmp_path / "canonical" / "pairs.json"
    canonical_pairs.parent.mkdir(parents=True)
    canonical_pairs.write_text('{"pairs": []}', encoding="utf-8")
    canonical_seed_scores = tmp_path / "canonical" / "seed_scores.json"
    canonical_seed_scores.write_text('{"seed_scores": []}', encoding="utf-8")
    canonical_daily = tmp_path / "canonical" / "daily_puzzles.json"
    canonical_daily.write_text('{"daily_puzzles": []}', encoding="utf-8")
    canonical_ghosts = tmp_path / "canonical" / "seed_ghosts.json"
    canonical_ghosts.write_text('{"seed_ghosts": []}', encoding="utf-8")

    report = apply_release_candidate(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        canonical_pairs_path=canonical_pairs,
        canonical_seed_scores_path=canonical_seed_scores,
        canonical_daily_puzzles_path=canonical_daily,
        canonical_seed_ghosts_path=canonical_ghosts,
        canonical_seed_ghost_image_dir=tmp_path / "canonical" / "seed_ghost_images",
        out_dir=tmp_path / "apply",
        season_id="season-test",
        apply=False,
    )

    assert report["valid"] is True
    assert report["applied"] is False
    assert {item["status"] for item in report["files"]} == {"would_write"}
    assert canonical_pairs.read_text(encoding="utf-8") == '{"pairs": []}'
    assert not (tmp_path / "canonical" / "seed_ghost_images").exists()


def test_apply_release_candidate_writes_canonical_files_and_ghost_images(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture_with_ghosts(tmp_path)
    canonical_dir = tmp_path / "canonical"

    report = apply_release_candidate(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        canonical_pairs_path=canonical_dir / "pairs.json",
        canonical_seed_scores_path=canonical_dir / "seed_scores.json",
        canonical_daily_puzzles_path=canonical_dir / "daily_puzzles.json",
        canonical_seed_ghosts_path=canonical_dir / "seed_ghosts.json",
        canonical_seed_ghost_image_dir=canonical_dir / "seed_ghost_images",
        out_dir=tmp_path / "apply",
        season_id="season-test",
        apply=True,
    )

    assert report["valid"] is True
    assert report["applied"] is True
    assert "apply wrote merged scoring data" in report["warnings"][0]
    assert "orange_to_tennis_ball" in (canonical_dir / "pairs.json").read_text(encoding="utf-8")
    assert "2026-07-06" in (canonical_dir / "daily_puzzles.json").read_text(encoding="utf-8")
    seed_ghost_payload = json.loads((canonical_dir / "seed_ghosts.json").read_text(encoding="utf-8"))
    assert len(seed_ghost_payload["seed_ghosts"]) == 2
    for ghost in seed_ghost_payload["seed_ghosts"]:
        assert ghost["image_ref"].startswith("file:")
        assert Path(ghost["image_ref"].removeprefix("file:")).exists()


def test_rollback_release_candidate_restores_backups_and_removes_new_images(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture_with_ghosts(tmp_path)
    canonical_dir = tmp_path / "canonical"
    canonical_image_dir = canonical_dir / "seed_ghost_images"
    canonical_image_dir.mkdir(parents=True)
    canonical_pairs = canonical_dir / "pairs.json"
    canonical_pairs.write_text('{"pairs": [{"pair_id": "old_pair"}]}', encoding="utf-8")
    canonical_seed_scores = canonical_dir / "seed_scores.json"
    canonical_seed_scores.write_text('{"seed_scores": []}', encoding="utf-8")
    canonical_daily = canonical_dir / "daily_puzzles.json"
    canonical_daily.write_text('{"daily_puzzles": []}', encoding="utf-8")
    canonical_ghosts = canonical_dir / "seed_ghosts.json"
    canonical_ghosts.write_text('{"seed_ghosts": []}', encoding="utf-8")

    apply_report = apply_release_candidate(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        canonical_pairs_path=canonical_pairs,
        canonical_seed_scores_path=canonical_seed_scores,
        canonical_daily_puzzles_path=canonical_daily,
        canonical_seed_ghosts_path=canonical_ghosts,
        canonical_seed_ghost_image_dir=canonical_image_dir,
        out_dir=tmp_path / "apply",
        season_id="season-test",
        apply=True,
    )
    apply_report_path = tmp_path / "apply" / "apply_release_candidate.json"
    created_images = list(canonical_image_dir.glob("*.png"))
    assert created_images

    dry_run = rollback_release_candidate(
        apply_report_path=apply_report_path,
        out_dir=tmp_path / "rollback-dry-run",
    )
    rollback = rollback_release_candidate(
        apply_report_path=apply_report_path,
        out_dir=tmp_path / "rollback",
        apply=True,
    )

    assert apply_report["applied"] is True
    assert dry_run["rolled_back"] is False
    assert {item["status"] for item in dry_run["files"]} == {"would_restore"}
    assert rollback["valid"] is True
    assert rollback["rolled_back"] is True
    assert canonical_pairs.read_text(encoding="utf-8") == '{"pairs": [{"pair_id": "old_pair"}]}'
    assert canonical_ghosts.read_text(encoding="utf-8") == '{"seed_ghosts": []}'
    assert not any(path.exists() for path in created_images)


def write_release_candidate_fixture_with_ghosts(tmp_path: Path) -> dict[str, Path]:
    paths = write_release_candidate_fixture(tmp_path)
    ghosts = build_seed_ghost_pack(
        daily_puzzles_path=paths["daily_puzzles"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        out_dir=tmp_path / "seed_ghost_images",
        season_id="season-test",
    )
    paths["seed_ghosts"].write_text(json.dumps({"seed_ghosts": ghosts}), encoding="utf-8")
    return paths


def write_release_candidate_fixture(tmp_path: Path) -> dict[str, Path]:
    ref_version = "approved-seed-heuristic-color-shape-v1-orange-tennis-ball-tau30-2026-06-30"
    paths = {
        "promotion_report": tmp_path / "promotion_report.json",
        "daily_plan_report": tmp_path / "daily_puzzle_plan.json",
        "pairs": tmp_path / "merged_pairs.json",
        "seed_scores": tmp_path / "merged_seed_scores.json",
        "daily_puzzles": tmp_path / "merged_daily_puzzles.json",
        "seed_ghosts": tmp_path / "planned_seed_ghosts.json",
    }
    paths["pairs"].write_text(
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
                            {"object_id": "baseball", "canonical_label": "baseball", "aliases": ["base ball"]},
                            {"object_id": "apple", "canonical_label": "apple", "aliases": ["apples"]},
                            {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    paths["seed_scores"].write_text(
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
    paths["daily_puzzles"].write_text(
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
    paths["promotion_report"].write_text(
        json.dumps(
            {
                "applied": False,
                "errors": [],
                "summary": {
                    "pairs_added": 1,
                    "pairs_reused": 0,
                    "seed_scores_added": 1,
                    "seed_scores_reused": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    paths["daily_plan_report"].write_text(
        json.dumps(
            {
                "applied": False,
                "errors": [],
                "planned": [
                    {
                        "date": "2026-07-06",
                        "pair_id": "orange_to_tennis_ball",
                        "ref_version": ref_version,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return paths
