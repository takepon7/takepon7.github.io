from __future__ import annotations

import argparse
import json
from pathlib import Path

from gitai_phase0.application import (
    BuildApprovedPairSeedQueueCommand,
    BuildApprovedPairSeedQueueUseCase,
)
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository, SqlitePairProposalRepository

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DB = ROOT / "data" / "runtime" / "play.sqlite"
DEFAULT_CATALOG = ROOT / "data" / "puzzle" / "object_catalog.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "phase2"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export approved player pair proposals as a seed-generation queue."
    )
    parser.add_argument("--runtime-db", type=Path, default=DEFAULT_RUNTIME_DB)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    result = BuildApprovedPairSeedQueueUseCase(
        object_catalog=ObjectCatalogRepository(args.catalog),
        proposals=SqlitePairProposalRepository(args.runtime_db),
    ).execute(BuildApprovedPairSeedQueueCommand(limit=args.limit))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "approved_pair_seed_queue.json"
    markdown_path = args.out_dir / "approved_pair_seed_queue.md"
    payload = {
        "entries": [entry.to_dict() for entry in result.entries],
        "skipped": [
            {
                "proposal_id": item.proposal_id,
                "pair_key": item.pair_key,
                "reason": item.reason,
            }
            for item in result.skipped
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


def render_markdown(payload: dict) -> str:
    lines = [
        "# Approved pair seed queue",
        "",
        f"- ready_entries: `{len(payload['entries'])}`",
        f"- skipped_entries: `{len(payload['skipped'])}`",
        "",
        "## Ready",
        "",
        "| pair_id | proposal_id | base | target | support | reviewer | note |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for entry in payload["entries"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    entry["pair_id"],
                    entry["proposal_id"],
                    entry["base"]["canonical_label"],
                    entry["target"]["canonical_label"],
                    str(entry["support_count"]),
                    entry["reviewer_id"] or "-",
                    entry["review_note"] or "-",
                ]
            )
            + " |"
        )
    if payload["skipped"]:
        lines.extend(
            [
                "",
                "## Skipped",
                "",
                "| proposal_id | pair_key | reason |",
                "| --- | --- | --- |",
            ]
        )
        for item in payload["skipped"]:
            lines.append(
                "| "
                + " | ".join([item["proposal_id"], item["pair_key"], item["reason"]])
                + " |"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
