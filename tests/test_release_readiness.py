from __future__ import annotations

import json
from pathlib import Path

from tools.apply_release_candidate import apply_release_candidate
from tools.build_seed_ghost_pack import build_seed_ghost_pack
from tools.smoke_release_readiness import smoke_release_readiness


def test_release_readiness_accepts_reviewable_bundle(tmp_path: Path) -> None:
    paths = write_release_candidate_fixture_with_ghosts(tmp_path)
    apply_report_path = write_applied_release_report(tmp_path, paths)
    web_dist = write_web_dist_fixture(tmp_path)
    static_smoke = tmp_path / "reports" / "phase3_static_smoke.json"
    static_smoke.parent.mkdir(parents=True)
    static_smoke.write_text(
        json.dumps({"checks": {"daily_puzzle_fetch": True, "share_card_endpoint": True}}),
        encoding="utf-8",
    )

    report = smoke_release_readiness(
        promotion_report_path=paths["promotion_report"],
        daily_plan_report_path=paths["daily_plan_report"],
        pairs_path=paths["pairs"],
        seed_scores_path=paths["seed_scores"],
        daily_puzzles_path=paths["daily_puzzles"],
        seed_ghosts_path=paths["seed_ghosts"],
        apply_report_path=apply_report_path,
        web_dist_dir=web_dist,
        static_smoke_path=static_smoke,
        out_dir=tmp_path / "readiness",
        season_id="season-test",
        today="2026-07-06",
    )

    assert report["valid"] is True
    assert report["summary"]["daily_count"] == 1
    assert report["summary"]["latest_pair_id"] == "orange_to_tennis_ball"
    assert report["api_smoke"]["valid"] is True
    assert report["api_smoke"]["score_deterministic"] is True
    assert report["first_play_api"]["valid"] is True
    assert report["first_play_api"]["summary"]["submission_id"]
    assert report["phase5_budget_smoke"]["gate_passed"] is True
    assert report["phase5_budget_smoke"]["degraded_gracefully"] is True
    assert report["rollback_dry_run"]["valid"] is True
    assert report["web_static"]["assets_ok"] is True
    assert (tmp_path / "readiness" / "release_readiness.json").exists()


def write_applied_release_report(tmp_path: Path, paths: dict[str, Path]) -> Path:
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

    apply_release_candidate(
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
    return tmp_path / "apply" / "apply_release_candidate.json"


def write_web_dist_fixture(tmp_path: Path) -> Path:
    web_dist = tmp_path / "web" / "dist"
    assets = web_dist / "assets"
    assets.mkdir(parents=True)
    (assets / "app.js").write_text("console.log('gitai');", encoding="utf-8")
    (assets / "app.css").write_text(".draw-canvas {}", encoding="utf-8")
    (web_dist / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="assets/app.css"></head>'
        '<body><script src="assets/app.js"></script></body></html>',
        encoding="utf-8",
    )
    return web_dist


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
