from __future__ import annotations

import argparse
import os
from pathlib import Path

from gitai_phase0.competition import DEFAULT_SEASON_ID
from gitai_phase0.season_ops import build_season_ops_report, write_season_ops_report

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    args = parse_args()
    report = build_season_ops_report(
        runtime_db=args.runtime_db,
        season_id=args.season_id,
        season_label=args.season_label,
        pinned_model_version=args.season_model_version,
    )
    json_path, markdown_path = write_season_ops_report(report, args.out_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"model_pin_ok={str(report.model_pin_ok).lower()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the Phase 5 season operations report.")
    parser.add_argument(
        "--runtime-db",
        type=Path,
        default=ROOT / "data" / "runtime" / "gitai.sqlite",
        help="Runtime SQLite database to inspect.",
    )
    parser.add_argument(
        "--season-id",
        default=os.environ.get("GITAI_SEASON_ID", DEFAULT_SEASON_ID),
        help="Season id to report.",
    )
    parser.add_argument(
        "--season-label",
        default=os.environ.get("GITAI_SEASON_LABEL", "Season 1"),
        help="Human-readable season label.",
    )
    parser.add_argument(
        "--season-model-version",
        default=os.environ.get("GITAI_SEASON_MODEL_VERSION", "heuristic-color-shape-v1"),
        help="Pinned judge model version for this season.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "reports" / "phase5",
        help="Directory for JSON and Markdown report outputs.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
