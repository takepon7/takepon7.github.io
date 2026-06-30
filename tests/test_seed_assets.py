from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from gitai_phase0.application import (
    ReviewPairProposalCommand,
    ReviewPairProposalUseCase,
    SubmitPairProposalCommand,
    SubmitPairProposalUseCase,
)
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository, SqlitePairProposalRepository
from gitai_phase0.repositories import image_fingerprint
from gitai_phase0.seed_asset_rendering import render_seed_asset_image
from tools.build_approved_seed_asset_pack import build_seed_asset_pack
from tools.promote_approved_seed_scores import promote_seed_scores
from tools.score_approved_seed_asset_pack import score_seed_asset_pack


def test_local_seed_asset_renderer_produces_quality_variants() -> None:
    weak = render_seed_asset_image("apple", "baseball", "weak")
    medium = render_seed_asset_image("apple", "baseball", "medium")
    strong = render_seed_asset_image("apple", "baseball", "strong")

    assert weak.size == (512, 512)
    assert len(
        {
            image_fingerprint(weak),
            image_fingerprint(medium),
            image_fingerprint(strong),
        }
    ) == 3


def test_approved_seed_asset_pack_writes_assets_cases_and_pairs(tmp_path: Path) -> None:
    catalog_path = Path("data/puzzle/object_catalog.json")
    catalog = ObjectCatalogRepository(catalog_path)
    proposals = SqlitePairProposalRepository(tmp_path / "runtime.sqlite")
    submitted = SubmitPairProposalUseCase(
        object_catalog=catalog,
        proposals=proposals,
    ).execute(
        SubmitPairProposalCommand(
            user_id="curator",
            base_label="apple",
            target_label="base ball",
            created_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
    )
    ReviewPairProposalUseCase(proposals=proposals).execute(
        ReviewPairProposalCommand(
            proposal_id=submitted.proposal.proposal_id,
            reviewer_id="ops",
            status="approved",
            note="seed next",
            reviewed_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
    )

    payload = build_seed_asset_pack(
        runtime_db=tmp_path / "runtime.sqlite",
        catalog_path=catalog_path,
        out_dir=tmp_path / "seed_assets",
        created_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert [pair["pair_id"] for pair in payload["pairs"]] == ["apple_to_baseball"]
    assert [asset["variant"] for asset in payload["seed_assets"]] == [
        "weak",
        "medium",
        "strong",
    ]
    assert [case["expected_rank"] for case in payload["cases"]] == [0, 1, 2]
    assert payload["skipped"] == []
    assert (tmp_path / "seed_assets" / "approved_seed_assets.json").exists()
    assert (tmp_path / "seed_assets" / "approved_seed_cases.json").exists()
    assert (tmp_path / "seed_assets" / "approved_seed_pairs.json").exists()
    for asset in payload["seed_assets"]:
        assert Path(asset["image_ref"].removeprefix("file:")).exists()


def test_approved_seed_asset_pack_scores_to_seed_scores_draft(tmp_path: Path) -> None:
    catalog_path = Path("data/puzzle/object_catalog.json")
    catalog = ObjectCatalogRepository(catalog_path)
    proposals = SqlitePairProposalRepository(tmp_path / "runtime.sqlite")
    submitted = SubmitPairProposalUseCase(
        object_catalog=catalog,
        proposals=proposals,
    ).execute(
        SubmitPairProposalCommand(
            user_id="curator",
            base_label="apple",
            target_label="base ball",
            created_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
    )
    ReviewPairProposalUseCase(proposals=proposals).execute(
        ReviewPairProposalCommand(
            proposal_id=submitted.proposal.proposal_id,
            reviewer_id="ops",
            status="approved",
            note="seed next",
            reviewed_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
    )
    pack_dir = tmp_path / "seed_assets"
    build_seed_asset_pack(
        runtime_db=tmp_path / "runtime.sqlite",
        catalog_path=catalog_path,
        out_dir=pack_dir,
        created_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    scored = score_seed_asset_pack(
        cases_path=pack_dir / "approved_seed_cases.json",
        images_root=pack_dir,
        out_dir=tmp_path / "seed_scores",
        model="heuristic",
        ocr="known_text",
        tau=30.0,
        ref_date="2026-06-30",
    )

    assert len(scored["seed_scores"]) == 1
    ref = scored["seed_scores"][0]
    assert ref["pair_id"] == "apple_to_baseball"
    assert ref["ref_version"] == "approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30"
    assert ref["scores_sorted"] == sorted(ref["scores_sorted"])
    assert len(ref["scores_sorted"]) == 3
    assert scored["qualities"][0]["pair_id"] == "apple_to_baseball"
    assert (tmp_path / "seed_scores" / "approved_seed_scores.json").exists()
    assert (tmp_path / "seed_scores" / "approved_measured_quality.json").exists()
    assert (tmp_path / "seed_scores" / "approved_seed_score_report.md").exists()


def test_promote_approved_seed_scores_preview_reuses_compatible_pair_and_adds_ref(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    draft_pairs_path = tmp_path / "draft_pairs.json"
    draft_seed_scores_path = tmp_path / "draft_seed_scores.json"
    measured_quality_path = tmp_path / "quality.json"
    out_dir = tmp_path / "promotion"
    pairs_path.write_text(
        """
        {
          "pairs": [
            {
              "pair_id": "apple_to_baseball",
              "base": {"object_id": "apple", "canonical_label": "apple", "aliases": ["apples"]},
              "target": {"object_id": "baseball", "canonical_label": "baseball", "aliases": ["base ball", "BASEBALL"]},
              "hard_negatives": [
                {"object_id": "tennis_ball", "canonical_label": "tennis ball", "aliases": ["tennisball"]},
                {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]},
                {"object_id": "orange", "canonical_label": "orange", "aliases": []}
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    seed_scores_path.write_text('{"seed_scores": []}', encoding="utf-8")
    draft_pairs_path.write_text(
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
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    draft_seed_scores_path.write_text(
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
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    measured_quality_path.write_text(
        """
        {
          "qualities": [
            {
              "ref_version": "approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30",
              "pair_id": "apple_to_baseball",
              "spread": 0.8,
              "p10": 0.1,
              "p50": 0.5,
              "p90": 0.9,
              "accepted": true,
              "measured_difficulty": "normal",
              "rejection_reasons": []
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    report = promote_seed_scores(
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        draft_pairs_path=draft_pairs_path,
        draft_seed_scores_path=draft_seed_scores_path,
        measured_quality_path=measured_quality_path,
        out_dir=out_dir,
        apply=False,
    )

    assert report["errors"] == []
    assert report["summary"]["pairs_reused"] == 1
    assert report["summary"]["seed_scores_added"] == 1
    assert report["applied"] is False
    assert '"seed_scores": []' in seed_scores_path.read_text(encoding="utf-8")
    merged = (out_dir / "merged_seed_scores.json").read_text(encoding="utf-8")
    assert "approved-seed-heuristic-color-shape-v1-apple-baseball-tau30-2026-06-30" in merged


def test_promote_approved_seed_scores_skips_rejected_quality(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    draft_pairs_path = tmp_path / "draft_pairs.json"
    draft_seed_scores_path = tmp_path / "draft_seed_scores.json"
    measured_quality_path = tmp_path / "quality.json"
    pairs_path.write_text(
        '{"pairs": [{"pair_id":"a_to_b","base":{"object_id":"a","canonical_label":"a","aliases":[]},"target":{"object_id":"b","canonical_label":"b","aliases":[]},"hard_negatives":[]}]}',
        encoding="utf-8",
    )
    seed_scores_path.write_text('{"seed_scores": []}', encoding="utf-8")
    draft_pairs_path.write_text(pairs_path.read_text(encoding="utf-8"), encoding="utf-8")
    draft_seed_scores_path.write_text(
        '{"seed_scores": [{"ref_version":"bad-ref","pair_id":"a_to_b","model_version":"heuristic-color-shape-v1","template_set_id":"drawing_v1","tau":30.0,"scores_sorted":[0.1],"stats":{"min":0.1,"p10":0.1,"p50":0.1,"p90":0.1,"max":0.1,"mean":0.1,"std":0.0}}]}',
        encoding="utf-8",
    )
    measured_quality_path.write_text(
        '{"qualities": [{"ref_version":"bad-ref","pair_id":"a_to_b","spread":0.0,"p10":0.1,"p50":0.1,"p90":0.1,"accepted":false,"measured_difficulty":"hard","rejection_reasons":["spread_below_floor"]}]}',
        encoding="utf-8",
    )

    report = promote_seed_scores(
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        draft_pairs_path=draft_pairs_path,
        draft_seed_scores_path=draft_seed_scores_path,
        measured_quality_path=measured_quality_path,
        out_dir=tmp_path / "promotion",
    )

    assert report["errors"] == []
    assert report["summary"]["seed_scores_added"] == 0
    assert report["seed_scores"][0]["status"] == "skipped_rejected_quality"
