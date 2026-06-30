from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from gitai_phase0.application import (
    BuildApprovedPairSeedQueueCommand,
    BuildApprovedPairSeedQueueUseCase,
)
from gitai_phase0.puzzle import ApprovedPairSeedQueueEntry, SeedAsset, SeedAssetQuality
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository, SqlitePairProposalRepository
from gitai_phase0.repositories import image_fingerprint
from gitai_phase0.seed_asset_rendering import LOCAL_SEED_ASSET_MODEL, render_seed_asset_image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DB = ROOT / "data" / "runtime" / "play.sqlite"
DEFAULT_CATALOG = ROOT / "data" / "puzzle" / "object_catalog.json"
DEFAULT_OUT_DIR = ROOT / "data" / "puzzle" / "approved_seed_asset_pack"
SEED_ASSET_VARIANTS: tuple[SeedAssetQuality, ...] = ("weak", "medium", "strong")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build local SeedAsset fixtures from approved player pair proposals."
    )
    parser.add_argument("--runtime-db", type=Path, default=DEFAULT_RUNTIME_DB)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--created-at", default="")
    args = parser.parse_args()

    created_at = (
        datetime.fromisoformat(args.created_at)
        if args.created_at
        else datetime.now(timezone.utc)
    )
    payload = build_seed_asset_pack(
        runtime_db=args.runtime_db,
        catalog_path=args.catalog,
        out_dir=args.out_dir,
        limit=args.limit,
        created_at=created_at,
    )
    print(f"Wrote {args.out_dir / 'approved_seed_assets.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_cases.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_pairs.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_asset_pack.md'}")
    print(f"Wrote {len(payload['seed_assets'])} seed asset images")


def build_seed_asset_pack(
    runtime_db: Path,
    catalog_path: Path,
    out_dir: Path,
    limit: int = 50,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    created_at = created_at or datetime.now(timezone.utc)
    image_dir = out_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    result = BuildApprovedPairSeedQueueUseCase(
        object_catalog=ObjectCatalogRepository(catalog_path),
        proposals=SqlitePairProposalRepository(runtime_db),
    ).execute(BuildApprovedPairSeedQueueCommand(limit=limit))

    seed_assets: list[SeedAsset] = []
    cases: list[dict[str, Any]] = []
    pairs_by_id: dict[str, dict[str, Any]] = {}
    for entry in result.entries:
        pair = entry.to_candidate_pair().to_pair_spec()
        pairs_by_id[pair.pair_id] = pair_to_dict(pair)
        for rank, variant in enumerate(SEED_ASSET_VARIANTS):
            image = render_seed_asset_image(
                base_object_id=entry.base.object_id,
                target_object_id=entry.target.object_id,
                quality=variant,
            )
            filename = f"{entry.pair_id}-{entry.proposal_id[:8]}-{variant}.png"
            path = image_dir / filename
            image.save(path)
            asset = SeedAsset(
                asset_id=image_fingerprint(image),
                proposal_id=entry.proposal_id,
                pair_id=entry.pair_id,
                variant=variant,
                image_ref=f"file:{relative_or_absolute(path)}",
                gen_model=LOCAL_SEED_ASSET_MODEL,
                gen_prompt=seed_asset_prompt(entry, variant),
                gen_params_hash=seed_asset_params_hash(entry, variant),
                created_at=created_at,
            )
            seed_assets.append(asset)
            cases.append(
                {
                    "case_id": f"{entry.pair_id}_{variant}_{entry.proposal_id[:8]}",
                    "image_path": f"images/{filename}",
                    "pair": pair_to_dict(pair),
                    "expected_quality": variant,
                    "expected_rank": rank,
                    "known_text": [],
                    "notes": f"Approved proposal seed asset: {entry.proposal_id}",
                }
            )

    payload: dict[str, Any] = {
        "seed_assets": [asset.to_dict() for asset in seed_assets],
        "cases": cases,
        "pairs": list(pairs_by_id.values()),
        "skipped": [
            {
                "proposal_id": item.proposal_id,
                "pair_key": item.pair_key,
                "reason": item.reason,
            }
            for item in result.skipped
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "approved_seed_assets.json", {"seed_assets": payload["seed_assets"]})
    write_json(out_dir / "approved_seed_cases.json", {"cases": payload["cases"]})
    write_json(out_dir / "approved_seed_pairs.json", {"pairs": payload["pairs"]})
    (out_dir / "approved_seed_asset_pack.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def seed_asset_prompt(entry: ApprovedPairSeedQueueEntry, variant: SeedAssetQuality) -> str:
    return (
        f"local deterministic {variant} disguise: "
        f"{entry.base.canonical_label} to {entry.target.canonical_label}"
    )


def seed_asset_params_hash(entry: ApprovedPairSeedQueueEntry, variant: SeedAssetQuality) -> str:
    payload = {
        "model": LOCAL_SEED_ASSET_MODEL,
        "pair_id": entry.pair_id,
        "proposal_id": entry.proposal_id,
        "variant": variant,
        "size": [512, 512],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def pair_to_dict(pair) -> dict[str, Any]:
    return {
        "pair_id": pair.pair_id,
        "base": object_label_to_dict(pair.base),
        "target": object_label_to_dict(pair.target),
        "hard_negatives": [object_label_to_dict(item) for item in pair.hard_negatives],
    }


def object_label_to_dict(obj) -> dict[str, Any]:
    return {
        "object_id": obj.object_id,
        "canonical_label": obj.canonical_label,
        "aliases": list(obj.aliases),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Approved SeedAsset pack",
        "",
        f"- pairs: `{len(payload['pairs'])}`",
        f"- seed_assets: `{len(payload['seed_assets'])}`",
        f"- cases: `{len(payload['cases'])}`",
        f"- skipped: `{len(payload['skipped'])}`",
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
    if payload["skipped"]:
        lines.extend(["", "## Skipped", "", "| proposal_id | pair_key | reason |", "| --- | --- | --- |"])
        for item in payload["skipped"]:
            lines.append("| " + " | ".join([item["proposal_id"], item["pair_key"], item["reason"]]) + " |")
    return "\n".join(lines) + "\n"


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
