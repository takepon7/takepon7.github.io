from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from gitai_phase0.budget_smoke import run_appraisal_budget_smoke, write_appraisal_budget_smoke_report

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="gitai-phase5-budget-") as tmpdir:
        report = run_appraisal_budget_smoke(
            runtime_db=Path(tmpdir) / "budget-smoke.sqlite",
            pairs_path=args.pairs,
            request_count=args.requests,
            daily_cap_units=args.daily_cap_units,
            user_daily_limit=args.user_daily_limit,
            mode=args.mode,
        )
    json_path, markdown_path = write_appraisal_budget_smoke_report(report, args.out_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"gate_passed={str(report.gate_passed).lower()}")
    if not report.gate_passed:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate Layer2 appraisal load against the Phase 5 budget gate.")
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--requests", type=int, default=25)
    parser.add_argument("--daily-cap-units", type=int, default=5)
    parser.add_argument("--user-daily-limit", type=int, default=25)
    parser.add_argument("--mode", choices=("hero", "on_demand"), default="hero")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "phase5")
    return parser.parse_args()


if __name__ == "__main__":
    main()
