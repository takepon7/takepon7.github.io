from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from gitai_phase0.puzzle import SeedAsset, SeedAssetQuality
from gitai_phase0.repositories import image_fingerprint
from gitai_phase0.seed_asset_rendering import LOCAL_SEED_ASSET_MODEL, render_seed_asset_image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAIRS = ROOT / "data" / "scoring" / "pairs.json"
DEFAULT_SEED_SCORES = ROOT / "data" / "scoring" / "seed_scores.json"
DEFAULT_OUT_DIR = ROOT / "data" / "puzzle" / "backlog_seed_asset_pack"
SEED_ASSET_VARIANTS: tuple[SeedAssetQuality, ...] = ("weak", "medium", "strong")

REAL_MODEL_PREFIXES = ("open_clip:", "siglip:")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build local SeedAsset fixtures directly from canonical pair specs. "
            "By default it targets pairs that still lack real-model SeedScore coverage, "
            "so the deterministic renderer can feed the open_clip/siglip scoring step."
        )
    )
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--seed-scores", type=Path, default=DEFAULT_SEED_SCORES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--pair-id",
        action="append",
        default=[],
        help="Explicit pair_id to include (repeatable). Overrides the backlog filter.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include every pair in --pairs, even ones already covered by a real model.",
    )
    parser.add_argument("--created-at", default="")
    args = parser.parse_args()

    created_at = (
        datetime.fromisoformat(args.created_at)
        if args.created_at
        else datetime.now(timezone.utc)
    )

    payload = build_pack_from_pairs(
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        out_dir=args.out_dir,
        explicit_pair_ids=list(args.pair_id),
        include_all=bool(args.all),
        created_at=created_at,
    )

    print(f"Wrote {args.out_dir / 'approved_seed_assets.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_cases.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_pairs.json'}")
    print(f"Wrote {args.out_dir / 'backlog_seed_asset_pack.md'}")
    print(
        f"Wrote {len(payload['seed_assets'])} seed asset images "
        f"for {len(payload['pairs'])} pairs"
    )


def build_pack_from_pairs(
    pairs_path: Path,
    seed_scores_path: Path,
    out_dir: Path,
    explicit_pair_ids: list[str] | None = None,
    include_all: bool = False,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    created_at = created_at or datetime.now(timezone.utc)
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    pairs = load_json(pairs_path).get("pairs", [])
    pair_by_id = {str(pair["pair_id"]): pair for pair in pairs}

    selected_ids = select_pair_ids(
        pair_by_id=pair_by_id,
        seed_scores_path=seed_scores_path,
        explicit_pair_ids=explicit_pair_ids or [],
        include_all=include_all,
    )

    seed_assets: list[SeedAsset] = []
    cases: list[dict[str, Any]] = []
    selected_pairs: list[dict[str, Any]] = []
    for pair_id in selected_ids:
        pair = pair_by_id[pair_id]
        selected_pairs.append(pair)
        base_id = str(pair["base"]["object_id"])
        target_id = str(pair["target"]["object_id"])
        synthetic_proposal_id = synthetic_proposal(pair_id)
        for rank, variant in enumerate(SEED_ASSET_VARIANTS):
            image = render_seed_asset_image(
                base_object_id=base_id,
                target_object_id=target_id,
                quality=variant,
            )
            filename = f"{pair_id}-{synthetic_proposal_id[:8]}-{variant}.png"
            path = image_dir / filename
            image.save(path)
            seed_assets.append(
                SeedAsset(
                    asset_id=image_fingerprint(image),
                    proposal_id=synthetic_proposal_id,
                    pair_id=pair_id,
                    variant=variant,
                    image_ref=f"file:{relative_or_absolute(path)}",
                    gen_model=LOCAL_SEED_ASSET_MODEL,
                    gen_prompt=(
                        f"local deterministic {variant} disguise: "
                        f"{pair['base']['canonical_label']} to {pair['target']['canonical_label']}"
                    ),
                    gen_params_hash=params_hash(pair_id, synthetic_proposal_id, variant),
                    created_at=created_at,
                )
            )
            cases.append(
                {
                    "case_id": f"{pair_id}_{variant}_{synthetic_proposal_id[:8]}",
                    "image_path": f"images/{filename}",
                    "pair": pair,
                    "expected_quality": variant,
                    "expected_rank": rank,
                    "known_text": [],
                    "notes": f"Canonical-pair seed asset for real-model coverage: {pair_id}",
                }
            )

    payload: dict[str, Any] = {
        "seed_assets": [asset.to_dict() for asset in seed_assets],
        "cases": cases,
        "pairs": selected_pairs,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "approved_seed_assets.json", {"seed_assets": payload["seed_assets"]})
    write_json(out_dir / "approved_seed_cases.json", {"cases": payload["cases"]})
    write_json(out_dir / "approved_seed_pairs.json", {"pairs": payload["pairs"]})
    (out_dir / "backlog_seed_asset_pack.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def select_pair_ids(
    pair_by_id: dict[str, dict[str, Any]],
    seed_scores_path: Path,
    explicit_pair_ids: list[str],
    include_all: bool,
) -> list[str]:
    if explicit_pair_ids:
        missing = [pid for pid in explicit_pair_ids if pid not in pair_by_id]
        if missing:
            raise SystemExit(f"Unknown pair_id(s): {', '.join(missing)}")
        return sorted(dict.fromkeys(explicit_pair_ids))
    if include_all:
        return sorted(pair_by_id)
    real_model_pairs = real_model_covered_pairs(seed_scores_path)
    backlog = sorted(pid for pid in pair_by_id if pid not in real_model_pairs)
    if not backlog:
        raise SystemExit("No backlog pairs: every pair already has real-model coverage.")
    return backlog


def real_model_covered_pairs(seed_scores_path: Path) -> set[str]:
    covered: set[str] = set()
    for ref in load_json(seed_scores_path).get("seed_scores", []):
        model_version = str(ref.get("model_version", ""))
        if model_version.startswith(REAL_MODEL_PREFIXES):
            covered.add(str(ref["pair_id"]))
    return covered


def synthetic_proposal(pair_id: str) -> str:
    digest = hashlib.sha256(f"backlog-seed::{pair_id}".encode("utf-8")).hexdigest()
    return f"backlog-{digest[:16]}"


def params_hash(pair_id: str, proposal_id: str, variant: SeedAssetQuality) -> str:
    payload = {
        "model": LOCAL_SEED_ASSET_MODEL,
        "pair_id": pair_id,
        "proposal_id": proposal_id,
        "variant": variant,
        "size": [512, 512],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Backlog SeedAsset pack",
        "",
        f"- pairs: `{len(payload['pairs'])}`",
        f"- seed_assets: `{len(payload['seed_assets'])}`",
        f"- cases: `{len(payload['cases'])}`",
        "",
        "## Assets",
        "",
        "| pair_id | variant | asset_id | image_ref |",
        "| --- | --- | --- | --- |",
    ]
    for asset in payload["seed_assets"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    asset["pair_id"],
                    asset["variant"],
                    asset["asset_id"][:12],
                    asset["image_ref"],
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
