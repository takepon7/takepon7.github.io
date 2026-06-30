from __future__ import annotations

from base64 import b64encode
from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile

from fastapi.testclient import TestClient
import pytest

from gitai_phase0.application import DrawingVerification
from gitai_phase0.api import AppState, build_season_from_env, build_state_from_env, create_app
from gitai_phase0.commentary import AppraisalComment, NullLayer2AppraisalActor
from gitai_phase0.commentary_repositories import SqliteAppraisalRepository
from gitai_phase0.cosmetic_repositories import SqliteCosmeticRepository
from gitai_phase0.competition import SeasonSpec
from gitai_phase0.competition_repositories import SqliteSubmissionRepository
from gitai_phase0.domain import PairSpec
from gitai_phase0.entitlement_repositories import SqliteEntitlementRepository
from gitai_phase0.heuristic_judge import HeuristicJudge
from gitai_phase0.moderation import NullImageModerator
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository, SqlitePairProposalRepository
from gitai_phase0.repositories import (
    DailyPuzzleRepository,
    ImageFingerprintOcrScanner,
    PairRepository,
    SeedScoreRepository,
)
from gitai_phase0.share_card import ShareCard
from gitai_phase0.submission_images import MemorySubmissionImageStore


DATA_DIR = Path("data/scoring")
IMAGES = Path("data/phase0/images")
REF_VERSION = "phase0-heuristic-tau30-2026-06-29"


def test_score_endpoint_is_deterministic() -> None:
    client = client_for_tests()
    payload = payload_for("apple_baseball_good.png")
    first = client.post("/v1/score", json=payload)
    second = client.post("/v1/score", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    first_body = without_timestamp(first.json())
    second_body = without_timestamp(second.json())
    assert first_body == second_body
    assert first_body["comment"]["source"] == "template_bank"
    assert first_body["comment"]["line"]


def test_daily_puzzle_endpoint_returns_current_frozen_pair(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-06-29")
    client = client_for_tests()
    response = client.get("/v1/daily-puzzle")
    assert response.status_code == 200
    body = response.json()
    assert body["pair_id"] == "apple_to_baseball"
    assert body["ref_version"] == "phase0-heuristic-tau30-2026-06-29"
    assert body["base"]["canonical_label"] == "apple"
    assert body["target"]["canonical_label"] == "baseball"


def test_daily_puzzle_endpoint_returns_applied_release_day(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-07-06")
    client = client_for_tests()

    response = client.get("/v1/daily-puzzle")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-07-06"
    assert body["pair_id"] == "apple_to_baseball"
    assert body["ref_version"] == "approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30"


def test_api_state_can_use_release_preview_file_overrides(tmp_path: Path, monkeypatch) -> None:
    pairs_path = tmp_path / "merged_pairs.json"
    seed_scores_path = tmp_path / "merged_seed_scores.json"
    daily_puzzles_path = tmp_path / "merged_daily_puzzles.json"
    seed_ghosts_path = tmp_path / "planned_seed_ghosts.json"
    ref_version = "preview-heuristic-orange-tennis-ball"

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
    daily_puzzles_path.write_text(
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
    seed_ghosts_path.write_text(json.dumps({"seed_ghosts": []}), encoding="utf-8")

    monkeypatch.setenv("GITAI_PAIRS_PATH", str(pairs_path))
    monkeypatch.setenv("GITAI_SEED_SCORES_PATH", str(seed_scores_path))
    monkeypatch.setenv("GITAI_DAILY_PUZZLES_PATH", str(daily_puzzles_path))
    monkeypatch.setenv("GITAI_SEED_GHOSTS", str(seed_ghosts_path))
    monkeypatch.setenv("GITAI_RUNTIME_DB", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setenv("GITAI_IMAGE_STORE", str(tmp_path / "submissions"))
    monkeypatch.setenv("GITAI_MODEL", "heuristic")
    monkeypatch.setenv("GITAI_OCR", "none")
    monkeypatch.setenv("GITAI_MODERATION", "none")
    monkeypatch.setenv("GITAI_TODAY", "2026-07-06")

    client = TestClient(create_app(build_state_from_env()))
    response = client.get("/v1/daily-puzzle")

    assert response.status_code == 200
    body = response.json()
    assert body["pair_id"] == "orange_to_tennis_ball"
    assert body["ref_version"] == ref_version
    assert body["target"]["canonical_label"] == "tennis ball"


def test_default_cors_allows_vite_fallback_port() -> None:
    client = client_for_tests()

    response = client.options(
        "/v1/daily-puzzle",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_api_responses_include_public_security_headers() -> None:
    client = client_for_tests()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]


def test_api_can_serve_built_web_app_same_origin(tmp_path: Path, monkeypatch) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>gitai app</title>", encoding="utf-8")
    (static_dir / "privacy.html").write_text("<!doctype html><title>Privacy Policy</title>", encoding="utf-8")
    monkeypatch.setenv("GITAI_STATIC_DIR", str(static_dir))
    monkeypatch.setenv("GITAI_TODAY", "2026-06-29")
    client = client_for_tests()

    app_shell = client.get("/")
    privacy = client.get("/privacy.html")
    api = client.get("/v1/daily-puzzle")

    assert app_shell.status_code == 200
    assert "gitai app" in app_shell.text
    assert privacy.status_code == 200
    assert "Privacy Policy" in privacy.text
    assert api.status_code == 200
    assert api.json()["pair_id"] == "apple_to_baseball"


def test_api_static_web_mount_fails_fast_without_built_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GITAI_STATIC_DIR", str(tmp_path / "missing-dist"))

    with pytest.raises(RuntimeError, match="GITAI_STATIC_DIR"):
        client_for_tests()


def test_daily_puzzle_endpoint_can_use_compatible_dev_ref(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-06-29")
    monkeypatch.setenv("GITAI_DAILY_REF_VERSION", "phase0-open-clip-tau30-2026-06-29")
    client = client_for_tests(judge=OpenClipVersionOnlyJudge())
    response = client.get("/v1/daily-puzzle")
    assert response.status_code == 200
    assert response.json()["ref_version"] == "phase0-open-clip-tau30-2026-06-29"


def test_daily_puzzle_endpoint_auto_selects_compatible_model_ref(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-06-29")
    monkeypatch.delenv("GITAI_DAILY_REF_VERSION", raising=False)
    client = client_for_tests(judge=OpenClipVersionOnlyJudge())

    response = client.get("/v1/daily-puzzle")

    assert response.status_code == 200
    body = response.json()
    assert body["pair_id"] == "apple_to_baseball"
    assert body["ref_version"] == "phase0-open-clip-tau30-2026-06-29"


def test_daily_puzzle_endpoint_rejects_date_without_compatible_model_ref(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-07-02")
    monkeypatch.delenv("GITAI_DAILY_REF_VERSION", raising=False)
    client = client_for_tests(judge=OpenClipVersionOnlyJudge())

    response = client.get("/v1/daily-puzzle?date=2026-07-01")

    assert response.status_code == 404
    assert "No seed score ref for pair_id=orange_to_tennis_ball" in response.json()["detail"]


def test_daily_puzzle_endpoint_does_not_jump_to_future_pack_day(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-07-04")
    client = client_for_tests()
    response = client.get("/v1/daily-puzzle")
    assert response.status_code == 200
    body = response.json()
    assert body["pair_id"] == "book_to_car"
    assert body["ref_version"] == "phase2-heuristic-book-car-tau30-2026-06-29"
    assert body["base"]["canonical_label"] == "book"
    assert body["target"]["canonical_label"] == "car"


def test_daily_puzzles_endpoint_lists_available_days_only(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-07-02")
    client = client_for_tests()

    response = client.get("/v1/daily-puzzles")

    assert response.status_code == 200
    body = response.json()
    assert body["current_date"] == "2026-07-02"
    assert [entry["date"] for entry in body["entries"]] == [
        "2026-06-29",
        "2026-06-30",
        "2026-07-01",
        "2026-07-02",
    ]
    assert body["entries"][-1]["current"] is True
    assert body["entries"][-1]["pair_id"] == "tomato_to_baseball"


def test_daily_puzzle_endpoint_can_fetch_available_date(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_TODAY", "2026-07-02")
    client = client_for_tests()

    response = client.get("/v1/daily-puzzle?date=2026-07-01")
    future = client.get("/v1/daily-puzzle?date=2026-07-03")

    assert response.status_code == 200
    body = response.json()
    assert body["pair_id"] == "orange_to_tennis_ball"
    assert body["ref_version"] == "phase2-heuristic-orange-tennis-ball-tau30-2026-06-29"
    assert future.status_code == 404
    assert "not available yet" in future.json()["detail"]


def test_pair_proposal_endpoint_persists_auto_gated_candidate(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")

    response = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "apple", "target_label": "base ball"},
    )
    listing = client.get("/v1/pair-proposals?status=candidate")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "curator"
    assert body["pair_key"] == "object:apple->object:baseball"
    assert body["base_label"] == "apple"
    assert body["target_label"] == "base ball"
    assert body["status"] == "candidate"
    assert body["support_count"] == 1
    assert body["difficulty_prior"] > 0
    assert body["base"]["object_id"] == "apple"
    assert body["target"]["object_id"] == "baseball"
    assert [item["object_id"] for item in body["hard_negatives"]] == [
        "tennis_ball",
        "tomato",
        "orange",
    ]
    assert listing.status_code == 200
    assert listing.json()["entries"][0]["proposal_id"] == body["proposal_id"]
    assert listing.json()["entries"][0]["support_count"] == 1


def test_pair_proposal_endpoint_aggregates_duplicate_support(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")

    first = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator-a", "base_label": "apple", "target_label": "base ball"},
    )
    second = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator-b", "base_label": "apple", "target_label": "baseball"},
    )
    listing = client.get("/v1/pair-proposals?status=candidate")

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["proposal_id"] == first_body["proposal_id"]
    assert second_body["pair_key"] == "object:apple->object:baseball"
    assert second_body["support_count"] == 2
    assert second_body["last_supported_at"] >= first_body["last_supported_at"]
    assert listing.status_code == 200
    entries = listing.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["proposal_id"] == first_body["proposal_id"]
    assert entries[0]["support_count"] == 2


def test_pair_proposal_review_endpoint_approves_candidate(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    proposal = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "apple", "target_label": "base ball"},
    ).json()

    response = client.post(
        f"/v1/pair-proposals/{proposal['proposal_id']}/review",
        json={"reviewer_id": "ops", "status": "approved", "note": "seed next"},
    )
    approved = client.get("/v1/pair-proposals?status=approved")

    assert response.status_code == 200
    body = response.json()
    assert body["proposal_id"] == proposal["proposal_id"]
    assert body["status"] == "approved"
    assert body["rejection_reasons"] == []
    assert body["reviewer_id"] == "ops"
    assert body["review_note"] == "seed next"
    assert body["reviewed_at"] is not None
    assert approved.status_code == 200
    assert approved.json()["entries"][0]["proposal_id"] == proposal["proposal_id"]


def test_pair_seed_queue_endpoint_exports_approved_proposals(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    proposal = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "apple", "target_label": "base ball"},
    ).json()
    client.post(
        f"/v1/pair-proposals/{proposal['proposal_id']}/review",
        json={"reviewer_id": "ops", "status": "approved", "note": "seed next"},
    )

    response = client.get("/v1/pair-seed-queue")

    assert response.status_code == 200
    body = response.json()
    assert body["skipped"] == []
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["proposal_id"] == proposal["proposal_id"]
    assert entry["pair_id"] == "apple_to_baseball"
    assert entry["status"] == "ready_for_seed_generation"
    assert entry["base"]["object_id"] == "apple"
    assert entry["target"]["object_id"] == "baseball"
    assert [item["object_id"] for item in entry["hard_negatives"]] == [
        "tennis_ball",
        "tomato",
        "orange",
    ]
    assert entry["reviewer_id"] == "ops"
    assert entry["review_note"] == "seed next"


def test_pair_proposal_review_endpoint_blocks_approval_without_catalog_objects(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    proposal = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "dragonfruit", "target_label": "car"},
    ).json()

    response = client.post(
        f"/v1/pair-proposals/{proposal['proposal_id']}/review",
        json={"reviewer_id": "ops", "status": "approved"},
    )
    listing = client.get("/v1/pair-proposals?status=needs_catalog_review")

    assert response.status_code == 409
    assert "known catalog objects" in response.json()["detail"]
    assert listing.status_code == 200
    assert listing.json()["entries"][0]["proposal_id"] == proposal["proposal_id"]


def test_pair_proposal_review_endpoint_rejects_candidate(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    proposal = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "apple", "target_label": "base ball"},
    ).json()

    response = client.post(
        f"/v1/pair-proposals/{proposal['proposal_id']}/review",
        json={"reviewer_id": "ops", "status": "rejected", "note": "too similar to current pack"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reasons"] == ["operator_rejected"]
    assert body["review_note"] == "too similar to current pack"


def test_pair_proposal_repository_migrates_duplicate_old_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "submissions.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table pair_proposals (
                proposal_id text primary key,
                user_id text not null,
                base_label text not null,
                target_label text not null,
                base_object_id text not null default '',
                target_object_id text not null default '',
                status text not null,
                rejection_reasons text not null,
                difficulty_prior real,
                hard_negative_ids text not null,
                created_at text not null
            )
            """
        )
        conn.execute(
            """
            insert into pair_proposals (
                proposal_id, user_id, base_label, target_label,
                base_object_id, target_object_id, status, rejection_reasons,
                difficulty_prior, hard_negative_ids, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "old-a",
                "curator-a",
                "apple",
                "base ball",
                "apple",
                "baseball",
                "candidate",
                "[]",
                0.22,
                '["tennis_ball"]',
                "2026-06-30T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            insert into pair_proposals (
                proposal_id, user_id, base_label, target_label,
                base_object_id, target_object_id, status, rejection_reasons,
                difficulty_prior, hard_negative_ids, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "old-b",
                "curator-b",
                "apple",
                "baseball",
                "apple",
                "baseball",
                "candidate",
                "[]",
                0.22,
                '["tennis_ball"]',
                "2026-06-30T00:01:00+00:00",
            ),
        )

    repo = SqlitePairProposalRepository(db_path)
    entries = repo.list(status="candidate")

    assert len(entries) == 1
    assert entries[0].proposal_id == "old-a"
    assert entries[0].pair_key == "object:apple->object:baseball"
    assert entries[0].support_count == 2
    assert entries[0].last_supported_at.isoformat() == "2026-06-30T00:01:00+00:00"


def test_pair_proposal_endpoint_keeps_unknown_labels_for_review(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")

    response = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "dragonfruit", "target_label": "car"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_catalog_review"
    assert body["base"] is None
    assert body["target"]["object_id"] == "car"
    assert body["rejection_reasons"] == ["unknown_base_label"]


def test_pair_proposal_endpoint_rejects_same_label(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")

    response = client.post(
        "/v1/pair-proposals",
        json={"user_id": "curator", "base_label": "apple", "target_label": "apples"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reasons"] == ["same_object"]


def test_score_endpoint_hard_zeroes_text_attack() -> None:
    client = client_for_tests()
    response = client.post("/v1/score", json=payload_for("apple_baseball_text_attack.png"))
    assert response.status_code == 200
    body = response.json()
    assert body["raw"] == 0.0
    assert body["score"] == 0
    assert body["flags"]["ocr_cheat"] is True


def test_score_endpoint_orders_good_above_plain() -> None:
    client = client_for_tests()
    plain = client.post("/v1/score", json=payload_for("apple_plain.png")).json()
    good = client.post("/v1/score", json=payload_for("apple_baseball_good.png")).json()
    assert good["raw"] > plain["raw"]
    assert good["score"] > plain["score"]


def test_ref_version_model_mismatch_is_rejected() -> None:
    client = client_for_tests()
    payload = payload_for("apple_baseball_good.png")
    payload["ref_version"] = "phase0-open-clip-tau30-2026-06-29"
    response = client.post("/v1/score", json=payload)
    assert response.status_code == 409


def test_season_model_pin_rejects_mismatched_active_judge(monkeypatch) -> None:
    monkeypatch.setenv("GITAI_SEASON_ID", "season-2")
    monkeypatch.setenv("GITAI_SEASON_MODEL_VERSION", "open_clip:ViT-L-14:openai:fp32")

    with pytest.raises(ValueError, match="pins"):
        build_season_from_env("heuristic-color-shape-v1")


def test_submit_endpoint_persists_submission_and_returns_leaderboard(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    payload = payload_for("apple_baseball_good.png")
    payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "player-1",
            "display_name": "  phase   tester  ",
            "stroke_log": {"strokes": [{"points": [1, 2, 3]}, {"points": [4, 5]}]},
        }
    )

    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200
    body = submission.json()
    assert body["season_id"] == "season-1"
    assert body["rank"] == 1
    assert body["submission_id"]
    assert body["score"] > 0
    assert body["comment"]["source"] == "template_bank"
    assert body["comment"]["template_id"].startswith("ja-")
    assert [reward["cosmetic_id"] for reward in body["rewards"]] == [
        "palette-verdict",
        "palette-masterpiece",
    ]

    leaderboard = client.get("/v1/leaderboard?date=2026-06-29")
    assert leaderboard.status_code == 200
    entries = leaderboard.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["rank"] == 1
    assert entries[0]["season_id"] == "season-1"
    assert entries[0]["submission_id"] == body["submission_id"]
    assert entries[0]["user_id"] == "player-1"
    assert entries[0]["display_name"] == "phase tester"
    assert entries[0]["stroke_count"] == 2


def test_cosmetics_endpoint_lists_default_and_unlocked_rewards(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    before = client.get("/v1/cosmetics?user_id=reward-player")
    assert before.status_code == 200
    assert [item["cosmetic_id"] for item in before.json()["cosmetics"]] == ["palette-classic"]

    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "reward-player", "display_name": "reward-player"})
    first = client.post("/v1/submissions", json=payload)
    second = client.post("/v1/submissions", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert [item["cosmetic_id"] for item in first.json()["rewards"]] == [
        "palette-verdict",
        "palette-masterpiece",
    ]
    assert second.json()["rewards"] == []

    after = client.get("/v1/cosmetics?user_id=reward-player")
    assert after.status_code == 200
    assert [item["cosmetic_id"] for item in after.json()["cosmetics"]] == [
        "palette-classic",
        "palette-verdict",
        "palette-masterpiece",
    ]


def test_leaderboard_and_ghost_are_scoped_to_active_season(tmp_path: Path) -> None:
    db_path = tmp_path / "submissions.sqlite"
    season_one = client_for_tests(
        db_path=db_path,
        season=SeasonSpec("season-1", "Season 1", "heuristic-color-shape-v1"),
    )
    season_two = client_for_tests(
        db_path=db_path,
        season=SeasonSpec("season-2", "Season 2", "heuristic-color-shape-v1"),
    )
    payload_one = payload_for("apple_baseball_good.png")
    payload_one.update({"puzzle_date": "2026-06-29", "user_id": "s1", "display_name": "s1"})
    payload_two = payload_for("apple_baseball_good.png")
    payload_two.update({"puzzle_date": "2026-06-29", "user_id": "s2", "display_name": "s2"})

    first = season_one.post("/v1/submissions", json=payload_one)
    second = season_two.post("/v1/submissions", json=payload_two)
    assert first.status_code == 200
    assert second.status_code == 200

    season_one_board = season_one.get("/v1/leaderboard?date=2026-06-29").json()
    season_two_board = season_two.get("/v1/leaderboard?date=2026-06-29").json()
    assert season_one_board["season_id"] == "season-1"
    assert season_two_board["season_id"] == "season-2"
    assert [entry["user_id"] for entry in season_one_board["entries"]] == ["s1"]
    assert [entry["user_id"] for entry in season_two_board["entries"]] == ["s2"]

    explicit_old_board = season_two.get("/v1/leaderboard?date=2026-06-29&season_id=season-1").json()
    assert explicit_old_board["season_id"] == "season-1"
    assert [entry["user_id"] for entry in explicit_old_board["entries"]] == ["s1"]

    ghost = season_two.get("/v1/ghost?date=2026-06-29")
    assert ghost.status_code == 200
    assert ghost.json()["season_id"] == "season-2"
    assert ghost.json()["display_name"] == "s2"


def test_submit_endpoint_ranks_better_score_above_plain(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    plain_payload = payload_for("apple_plain.png")
    plain_payload.update({"puzzle_date": "2026-06-29", "user_id": "plain", "display_name": "plain"})
    good_payload = payload_for("apple_baseball_good.png")
    good_payload.update({"puzzle_date": "2026-06-29", "user_id": "good", "display_name": "good"})

    plain = client.post("/v1/submissions", json=plain_payload)
    good = client.post("/v1/submissions", json=good_payload)
    assert plain.status_code == 200
    assert good.status_code == 200
    assert good.json()["rank"] == 1

    entries = client.get("/v1/leaderboard?date=2026-06-29").json()["entries"]
    assert [entry["user_id"] for entry in entries] == ["good", "plain"]


def test_ghost_endpoint_returns_top_submission_image(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "ghost", "display_name": "ghost"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    ghost = client.get("/v1/ghost?date=2026-06-29")
    assert ghost.status_code == 200
    body = ghost.json()
    assert body["rank"] == 1
    assert body["submission_id"] == submission.json()["submission_id"]
    assert body["display_name"] == "ghost"
    assert body["image_b64"]


def test_ghost_endpoint_returns_replayable_stroke_log(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    stroke_log = {
        "strokes": [
            {
                "color": "#315f9d",
                "size": 18,
                "mode": "draw",
                "points": [
                    {"x": 250, "y": 300, "t": 0, "pressure": 0.5},
                    {"x": 350, "y": 320, "t": 10, "pressure": 0.5},
                ],
            }
        ]
    }
    payload = payload_for("apple_baseball_good.png")
    payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "ghost",
            "display_name": "ghost",
            "stroke_log": stroke_log,
        }
    )
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    ghost = client.get("/v1/ghost?date=2026-06-29")

    assert ghost.status_code == 200
    assert ghost.json()["stroke_log"] == stroke_log


def test_share_card_endpoint_returns_png_for_submission(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "share", "display_name": "share"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    response = client.get(f"/v1/share-card?submission_id={submission.json()['submission_id']}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_share_card_endpoint_uses_cached_appraisal_comment(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "submissions.sqlite"
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=db_path, image_store=image_store)
    monkeypatch.setenv("GITAI_PUBLIC_WEB_URL", "https://gitai.example")
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "share", "display_name": "share"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200
    submission_id = submission.json()["submission_id"]
    cached = AppraisalComment(
        line="これは由緒ある野球ボールです。",
        mood="smug",
        source="layer2",
        template_id="scripted",
    )
    SqliteAppraisalRepository(db_path).cache_comment(
        submission_id=submission_id,
        user_id="share",
        comment=cached,
        actor_version="scripted-test",
        cost_units=0,
        day=date(2026, 6, 29),
    )
    captured: dict[str, AppraisalComment | str | None] = {}

    def fake_build_share_card(**kwargs) -> ShareCard:
        captured["comment"] = kwargs["comment"]
        captured["public_url"] = kwargs["public_url"]
        return ShareCard(png=b"\x89PNG\r\n\x1a\ncached", filename="cached.png")

    monkeypatch.setattr("gitai_phase0.api.build_share_card", fake_build_share_card)

    response = client.get(f"/v1/share-card?submission_id={submission_id}")

    assert response.status_code == 200
    assert captured["comment"] == cached
    assert captured["public_url"] == "https://gitai.example"


def test_share_card_endpoint_rejects_ocr_cheat(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    payload = payload_for("apple_baseball_text_attack.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "cheat", "display_name": "cheat"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    response = client.get(f"/v1/share-card?submission_id={submission.json()['submission_id']}")
    assert response.status_code == 403
    assert response.json()["detail"] == "submission is not shareable"


def test_moderation_flag_excludes_submission_from_public_surfaces(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(
        db_path=tmp_path / "submissions.sqlite",
        image_store=image_store,
        moderator=FlaggingModerator(),
    )
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "flagged", "display_name": "flagged"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200
    assert submission.json()["flags"]["moderation"] == "flag"

    board = client.get("/v1/leaderboard?date=2026-06-29&kind=score")
    assert board.status_code == 200
    assert board.json()["entries"] == []

    response = client.get(f"/v1/share-card?submission_id={submission.json()['submission_id']}")
    assert response.status_code == 403
    assert response.json()["detail"] == "submission is not shareable"


def test_efficiency_leaderboard_and_ghost_use_kind(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    slow_payload = payload_for("apple_baseball_good.png")
    slow_payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "slow",
            "display_name": "slow",
            "stroke_log": {"strokes": [{}, {}, {}, {}, {}]},
        }
    )
    fast_payload = payload_for("apple_baseball_good.png")
    fast_payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "fast",
            "display_name": "fast",
            "stroke_log": {"strokes": [{}]},
        }
    )
    assert client.post("/v1/submissions", json=slow_payload).status_code == 200
    assert client.post("/v1/submissions", json=fast_payload).status_code == 200

    board = client.get("/v1/leaderboard?date=2026-06-29&kind=efficiency")
    assert board.status_code == 200
    body = board.json()
    assert body["kind"] == "efficiency"
    assert [entry["user_id"] for entry in body["entries"]] == ["fast", "slow"]

    ghost = client.get("/v1/ghost?date=2026-06-29&kind=efficiency")
    assert ghost.status_code == 200
    assert ghost.json()["kind"] == "efficiency"
    assert ghost.json()["display_name"] == "fast"


def test_friend_leaderboard_requires_code() -> None:
    client = client_for_tests()
    response = client.get("/v1/leaderboard?kind=friend")
    assert response.status_code == 400
    assert response.json()["detail"] == "friend_code is required for friend leaderboard"

    ghost = client.get("/v1/ghost?kind=friend")
    assert ghost.status_code == 400
    assert ghost.json()["detail"] == "friend_code is required for friend leaderboard"


def test_friend_leaderboard_and_ghost_filter_submissions(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    room_a_payload = payload_for("apple_baseball_good.png")
    room_a_payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "room-a",
            "display_name": "room a",
            "friend_code": "room-a",
        }
    )
    room_b_payload = payload_for("apple_baseball_good.png")
    room_b_payload.update(
        {
            "puzzle_date": "2026-06-29",
            "user_id": "room-b",
            "display_name": "room b",
            "friend_code": "room-b",
        }
    )
    room_a = client.post("/v1/submissions", json=room_a_payload)
    room_b = client.post("/v1/submissions", json=room_b_payload)
    assert room_a.status_code == 200
    assert room_a.json()["rank"] == 1
    assert room_b.status_code == 200
    assert room_b.json()["rank"] == 2

    board = client.get("/v1/leaderboard?date=2026-06-29&kind=friend&friend_code=Room-A")
    assert board.status_code == 200
    body = board.json()
    assert body["kind"] == "friend"
    assert [entry["user_id"] for entry in body["entries"]] == ["room-a"]
    assert body["entries"][0]["friend_code"] == "ROOM-A"

    ghost = client.get("/v1/ghost?date=2026-06-29&kind=friend&friend_code=room-a")
    assert ghost.status_code == 200
    assert ghost.json()["kind"] == "friend"
    assert ghost.json()["submission_id"] == room_a.json()["submission_id"]
    assert ghost.json()["display_name"] == "room a"


def test_funny_votes_are_unique_and_power_funny_ladder(tmp_path: Path) -> None:
    image_store = MemorySubmissionImageStore()
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", image_store=image_store)
    funny_payload = payload_for("apple_baseball_good.png")
    funny_payload.update({"puzzle_date": "2026-06-29", "user_id": "artist", "display_name": "artist"})
    rival_payload = payload_for("apple_plain.png")
    rival_payload.update({"puzzle_date": "2026-06-29", "user_id": "rival", "display_name": "rival"})
    funny_submission = client.post("/v1/submissions", json=funny_payload)
    rival_submission = client.post("/v1/submissions", json=rival_payload)
    assert funny_submission.status_code == 200
    assert rival_submission.status_code == 200

    funny_id = funny_submission.json()["submission_id"]
    rival_id = rival_submission.json()["submission_id"]
    self_vote = client.post("/v1/funny-votes", json={"submission_id": funny_id, "user_id": "artist"})
    first_vote = client.post("/v1/funny-votes", json={"submission_id": funny_id, "user_id": "viewer"})
    duplicate_vote = client.post("/v1/funny-votes", json={"submission_id": funny_id, "user_id": "viewer"})
    rival_vote = client.post("/v1/funny-votes", json={"submission_id": rival_id, "user_id": "viewer"})

    assert self_vote.status_code == 409
    assert self_vote.json()["detail"] == "cannot vote for your own submission"
    assert first_vote.status_code == 200
    assert first_vote.json() == {"submission_id": funny_id, "funny_votes": 1, "accepted": True}
    assert duplicate_vote.status_code == 200
    assert duplicate_vote.json() == {"submission_id": funny_id, "funny_votes": 1, "accepted": False}
    assert rival_vote.status_code == 200

    board = client.get("/v1/leaderboard?date=2026-06-29&kind=funny")
    assert board.status_code == 200
    body = board.json()
    assert body["kind"] == "funny"
    assert [entry["submission_id"] for entry in body["entries"]] == [funny_id, rival_id]
    assert body["entries"][0]["funny_votes"] == 1

    ghost = client.get("/v1/ghost?date=2026-06-29&kind=funny")
    assert ghost.status_code == 200
    assert ghost.json()["kind"] == "funny"
    assert ghost.json()["submission_id"] == funny_id
    assert ghost.json()["funny_votes"] == 1


def test_unknown_leaderboard_kind_is_rejected() -> None:
    client = client_for_tests()
    response = client.get("/v1/leaderboard?kind=weird")
    assert response.status_code == 400
    assert response.json()["detail"] == "kind must be score, efficiency, friend, or funny"


def test_submit_endpoint_rate_limits_bursts(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")

    responses = []
    for index in range(6):
        payload = payload_for("apple_baseball_good.png")
        payload.update({"puzzle_date": "2026-06-29", "user_id": "bursty", "display_name": f"bursty-{index}"})
        responses.append(client.post("/v1/submissions", json=payload))

    assert [response.status_code for response in responses[:5]] == [200, 200, 200, 200, 200]
    assert responses[5].status_code == 429
    assert responses[5].json()["detail"] == "rate limit exceeded"
    assert int(responses[5].headers["retry-after"]) > 0


def test_submit_endpoint_enforces_daily_submission_limit(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite", daily_submission_limit=1)
    first_payload = payload_for("apple_baseball_good.png")
    first_payload.update({"puzzle_date": "2026-06-29", "user_id": "daily-player", "display_name": "daily-player"})
    second_payload = payload_for("apple_baseball_poor.png")
    second_payload.update({"puzzle_date": "2026-06-29", "user_id": "daily-player", "display_name": "daily-player"})

    first = client.post("/v1/submissions", json=first_payload)
    second = client.post("/v1/submissions", json=second_payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "daily submission limit exceeded"


def test_submit_endpoint_allows_premium_past_daily_submission_limit(tmp_path: Path) -> None:
    client = client_for_tests(
        db_path=tmp_path / "submissions.sqlite",
        daily_submission_limit=1,
        premium_user_ids={"premium-player"},
    )
    first_payload = payload_for("apple_baseball_good.png")
    first_payload.update({"puzzle_date": "2026-06-29", "user_id": "premium-player", "display_name": "premium-player"})
    second_payload = payload_for("apple_baseball_poor.png")
    second_payload.update({"puzzle_date": "2026-06-29", "user_id": "premium-player", "display_name": "premium-player"})

    assert client.post("/v1/submissions", json=first_payload).status_code == 200
    assert client.post("/v1/submissions", json=second_payload).status_code == 200


def test_redeemed_premium_pass_allows_past_daily_submission_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "submissions.sqlite"
    entitlements = SqliteEntitlementRepository(db_path)
    entitlements.seed_redeem_code("founder-pass", max_redemptions=1)
    client = client_for_tests(
        db_path=db_path,
        daily_submission_limit=1,
        entitlements=entitlements,
    )

    before = client.get("/v1/premium?user_id=redeemer")
    redeemed = client.post("/v1/premium/redeem", json={"user_id": "redeemer", "code": "founder-pass"})
    after = client.get("/v1/premium?user_id=redeemer")
    exhausted = client.post("/v1/premium/redeem", json={"user_id": "other", "code": "founder-pass"})
    first_payload = payload_for("apple_baseball_good.png")
    first_payload.update({"puzzle_date": "2026-06-29", "user_id": "redeemer", "display_name": "redeemer"})
    second_payload = payload_for("apple_baseball_poor.png")
    second_payload.update({"puzzle_date": "2026-06-29", "user_id": "redeemer", "display_name": "redeemer"})

    assert before.status_code == 200
    assert before.json()["premium"] is False
    assert redeemed.status_code == 200
    assert redeemed.json()["status"] == "redeemed"
    assert redeemed.json()["premium"] is True
    assert after.json()["premium"] is True
    assert after.json()["source"] == "redeem:FOUNDER-PASS"
    assert exhausted.json()["status"] == "exhausted"
    assert exhausted.json()["premium"] is False
    assert client.post("/v1/submissions", json=first_payload).status_code == 200
    assert client.post("/v1/submissions", json=second_payload).status_code == 200


def test_appraisal_comment_endpoint_falls_back_without_layer2(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "artist", "display_name": "artist"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    response = client.post(
        "/v1/appraisal-comments",
        json={"submission_id": submission.json()["submission_id"], "user_id": "artist"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback_unavailable"
    assert body["daily_spend"] == 0
    assert body["daily_cap"] == 100
    assert body["user_remaining"] == 3
    assert body["comment"]["source"] == "template_bank"


def test_appraisal_comment_hero_mode_requires_high_percentile(tmp_path: Path) -> None:
    client = client_for_tests(db_path=tmp_path / "submissions.sqlite")
    payload = payload_for("apple_baseball_poor.png")
    payload.update({"puzzle_date": "2026-06-29", "user_id": "artist", "display_name": "artist"})
    submission = client.post("/v1/submissions", json=payload)
    assert submission.status_code == 200

    response = client.post(
        "/v1/appraisal-comments",
        json={"submission_id": submission.json()["submission_id"], "user_id": "artist", "mode": "hero"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback_hero_gate"
    assert body["daily_spend"] == 0
    assert body["comment"]["source"] == "template_bank"


def test_submit_endpoint_rejects_unreplayable_ranked_image(tmp_path: Path) -> None:
    client = client_for_tests(
        db_path=tmp_path / "submissions.sqlite",
        drawing_verifier=RejectingDrawingVerifier(),
    )
    payload = payload_for("apple_baseball_good.png")
    payload.update({"puzzle_date": "2026-06-29", "stroke_log": {"strokes": []}})

    response = client.post("/v1/submissions", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "submitted image does not match stroke replay"


def client_for_tests(
    judge=None,
    db_path: Path | None = None,
    drawing_verifier=None,
    image_store=None,
    daily_submission_limit: int = 100,
    premium_user_ids: set[str] | None = None,
    entitlements=None,
    moderator=None,
    season: SeasonSpec | None = None,
) -> TestClient:
    if db_path is None:
        db_path = Path(tempfile.mkdtemp(prefix="gitai-test-")) / "submissions.sqlite"
    state = AppState(
        pairs=PairRepository(DATA_DIR / "pairs.json"),
        seed_scores=SeedScoreRepository(DATA_DIR / "seed_scores.json"),
        daily_puzzles=DailyPuzzleRepository(Path("data/puzzle/daily_puzzles.json")),
        object_catalog=ObjectCatalogRepository(Path("data/puzzle/object_catalog.json")),
        pair_proposals=SqlitePairProposalRepository(db_path),
        submissions=SqliteSubmissionRepository(db_path),
        submission_images=image_store or MemorySubmissionImageStore(),
        appraisals=SqliteAppraisalRepository(db_path),
        cosmetics=SqliteCosmeticRepository(db_path),
        entitlements=entitlements or SqliteEntitlementRepository(db_path),
        appraisal_actor=NullLayer2AppraisalActor(),
        daily_llm_spend_cap=100,
        user_daily_comment_limit=3,
        daily_submission_limit=daily_submission_limit,
        premium_user_ids=premium_user_ids or set(),
        season=season or SeasonSpec("season-1", "Season 1", "heuristic-color-shape-v1"),
        drawing_verifier=drawing_verifier or AcceptingDrawingVerifier(),
        judge=judge or HeuristicJudge(),
        ocr=ImageFingerprintOcrScanner(DATA_DIR / "ocr_fixtures.json"),
        moderator=moderator or NullImageModerator(),
    )
    return TestClient(create_app(state))


def payload_for(filename: str) -> dict:
    image_b64 = b64encode((IMAGES / filename).read_bytes()).decode("ascii")
    return {
        "image_b64": image_b64,
        "pair_id": "apple_to_baseball",
        "ref_version": REF_VERSION,
    }


def without_timestamp(body: dict) -> dict:
    copied = dict(body)
    copied.pop("computed_at", None)
    return copied


class OpenClipVersionOnlyJudge:
    model_version = "open_clip:ViT-L-14:openai:fp32"

    def encode_image(self, image):
        raise AssertionError("daily puzzle endpoint must not encode images")

    def encode_text(self, label, template_set):
        raise AssertionError("daily puzzle endpoint must not encode text")


class AcceptingDrawingVerifier:
    def verify(self, image, pair: PairSpec, stroke_log) -> DrawingVerification:
        return DrawingVerification(True, 0.0, "ok")


class RejectingDrawingVerifier:
    def verify(self, image, pair: PairSpec, stroke_log) -> DrawingVerification:
        return DrawingVerification(False, 1.0, "submitted image does not match stroke replay")


class FlaggingModerator:
    def moderate(self, image, case=None) -> str:
        del image, case
        return "flag"
