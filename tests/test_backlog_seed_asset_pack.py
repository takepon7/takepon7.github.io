from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from tools.build_seed_asset_pack_from_pairs import build_pack_from_pairs


def _write_pairs(path: Path) -> None:
    pairs = {
        "pairs": [
            {
                "pair_id": "apple_to_baseball",
                "base": {"object_id": "apple", "canonical_label": "apple", "aliases": []},
                "target": {"object_id": "baseball", "canonical_label": "baseball", "aliases": []},
                "hard_negatives": [],
            },
            {
                "pair_id": "tomato_to_baseball",
                "base": {"object_id": "tomato", "canonical_label": "tomato", "aliases": []},
                "target": {"object_id": "baseball", "canonical_label": "baseball", "aliases": []},
                "hard_negatives": [],
            },
        ]
    }
    path.write_text(json.dumps(pairs), encoding="utf-8")


def _write_seed_scores(path: Path) -> None:
    # apple already has a real-model ref; tomato is heuristic-only backlog.
    seed_scores = {
        "seed_scores": [
            {
                "pair_id": "apple_to_baseball",
                "model_version": "open_clip:ViT-L-14:openai:fp32",
                "ref_version": "ref-apple-real",
            },
            {
                "pair_id": "tomato_to_baseball",
                "model_version": "heuristic-color-shape-v1",
                "ref_version": "ref-tomato-heuristic",
            },
        ]
    }
    path.write_text(json.dumps(seed_scores), encoding="utf-8")


def test_backlog_pack_targets_only_real_model_uncovered_pairs(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    out_dir = tmp_path / "pack"
    _write_pairs(pairs_path)
    _write_seed_scores(seed_scores_path)

    payload = build_pack_from_pairs(
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=out_dir,
    )

    selected_ids = sorted({pair["pair_id"] for pair in payload["pairs"]})
    assert selected_ids == ["tomato_to_baseball"]
    # 1 backlog pair x 3 quality variants.
    assert len(payload["seed_assets"]) == 3
    assert len(payload["cases"]) == 3

    cases = json.loads((out_dir / "approved_seed_cases.json").read_text(encoding="utf-8"))["cases"]
    variants = sorted(case["expected_quality"] for case in cases)
    assert variants == ["medium", "strong", "weak"]
    for case in cases:
        image = Image.open(out_dir / case["image_path"])
        assert image.size == (512, 512)


def test_backlog_pack_explicit_pair_overrides_filter(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    seed_scores_path = tmp_path / "seed_scores.json"
    out_dir = tmp_path / "pack"
    _write_pairs(pairs_path)
    _write_seed_scores(seed_scores_path)

    payload = build_pack_from_pairs(
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        out_dir=out_dir,
        explicit_pair_ids=["apple_to_baseball"],
    )

    assert [pair["pair_id"] for pair in payload["pairs"]] == ["apple_to_baseball"]
