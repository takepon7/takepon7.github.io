from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from gitai_phase0.puzzle import CurationPolicy, DailyPuzzle
from gitai_phase0.repositories import SeedScoreRef

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DAILY = ROOT / "data" / "puzzle" / "daily_puzzles.json"
DEFAULT_PAIRS = ROOT / "data" / "scoring" / "pairs.json"
DEFAULT_SEED_SCORES = ROOT / "data" / "scoring" / "seed_scores.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "phase2" / "daily_puzzle_plan"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan DailyPuzzle entries from accepted SeedScores refs."
    )
    parser.add_argument("--daily-puzzles", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--seed-scores", type=Path, default=DEFAULT_SEED_SCORES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--start-date", default="")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--ref-prefix", default="approved-seed-")
    parser.add_argument("--model-version", default="")
    parser.add_argument("--frozen-at", default="")
    parser.add_argument("--allow-repeat-pairs", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = plan_daily_puzzles(
        daily_puzzles_path=args.daily_puzzles,
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        out_dir=args.out_dir,
        start_date=(date.fromisoformat(args.start_date) if args.start_date else None),
        days=args.days,
        ref_prefix=args.ref_prefix,
        model_version=args.model_version,
        frozen_at=(datetime.fromisoformat(args.frozen_at) if args.frozen_at else None),
        allow_repeat_pairs=args.allow_repeat_pairs,
        apply=args.apply,
    )
    mode = "applied" if report["applied"] else "preview"
    print(f"Wrote {args.out_dir / 'daily_puzzle_plan.json'}")
    print(f"Wrote {args.out_dir / 'daily_puzzle_plan.md'}")
    print(f"Wrote {args.out_dir / 'merged_daily_puzzles.json'}")
    print(f"{mode}: {len(report['planned'])} DailyPuzzle entries planned")


def plan_daily_puzzles(
    daily_puzzles_path: Path,
    pairs_path: Path,
    seed_scores_path: Path,
    out_dir: Path,
    start_date: date | None = None,
    days: int = 7,
    ref_prefix: str = "approved-seed-",
    model_version: str = "",
    frozen_at: datetime | None = None,
    allow_repeat_pairs: bool = False,
    apply: bool = False,
) -> dict[str, Any]:
    daily_payload = load_json(daily_puzzles_path)
    pair_payload = load_json(pairs_path)
    seed_payload = load_json(seed_scores_path)
    existing_daily = [
        DailyPuzzle(
            date=date.fromisoformat(str(item["date"])),
            pair_id=str(item["pair_id"]),
            ref_version=str(item["ref_version"]),
            frozen_at=datetime.fromisoformat(str(item["frozen_at"])),
        )
        for item in daily_payload.get("daily_puzzles", [])
    ]
    pair_ids = {str(item["pair_id"]) for item in pair_payload.get("pairs", [])}
    refs = [SeedScoreRef.from_dict(item) for item in seed_payload.get("seed_scores", [])]
    policy = CurationPolicy()
    frozen_at = frozen_at or datetime.now(timezone.utc)
    start_date = start_date or next_daily_date(existing_daily)
    report: dict[str, Any] = {
        "applied": apply,
        "start_date": start_date.isoformat(),
        "days": max(0, days),
        "ref_prefix": ref_prefix,
        "model_version": model_version,
        "allow_repeat_pairs": allow_repeat_pairs,
        "planned": [],
        "skipped": [],
        "errors": [],
    }

    existing_dates = {item.date for item in existing_daily}
    existing_pairs = {item.pair_id for item in existing_daily}
    existing_refs = {item.ref_version for item in existing_daily}
    for index in range(max(0, days)):
        candidate_date = start_date + timedelta(days=index)
        if candidate_date in existing_dates:
            report["errors"].append(
                {
                    "kind": "date_conflict",
                    "date": candidate_date.isoformat(),
                    "detail": "DailyPuzzle date already exists",
                }
            )

    eligible: list[SeedScoreRef] = []
    for ref in sorted(refs, key=lambda item: (item.pair_id, item.ref_version)):
        if ref_prefix and not ref.ref_version.startswith(ref_prefix):
            continue
        if model_version and ref.model_version != model_version:
            report["skipped"].append(skip_ref(ref, "model_version_mismatch"))
            continue
        if ref.pair_id not in pair_ids:
            report["errors"].append(
                {
                    "kind": "missing_pair",
                    "ref_version": ref.ref_version,
                    "pair_id": ref.pair_id,
                    "detail": "SeedScores ref references an unknown pair",
                }
            )
            continue
        if ref.ref_version in existing_refs:
            report["skipped"].append(skip_ref(ref, "ref_already_scheduled"))
            continue
        if ref.pair_id in existing_pairs and not allow_repeat_pairs:
            report["skipped"].append(skip_ref(ref, "pair_already_scheduled"))
            continue
        quality = policy.evaluate_seed_scores(ref)
        if not quality.accepted:
            report["skipped"].append(
                {
                    **skip_ref(ref, "quality_rejected"),
                    "rejection_reasons": list(quality.rejection_reasons),
                }
            )
            continue
        eligible.append(ref)

    planned = eligible[: max(0, days)]
    merged_daily = [
        item.to_dict()
        for item in sorted(existing_daily, key=lambda item: item.date)
    ]
    for offset, ref in enumerate(planned):
        puzzle = DailyPuzzle(
            date=start_date + timedelta(days=offset),
            pair_id=ref.pair_id,
            ref_version=ref.ref_version,
            frozen_at=frozen_at,
        )
        merged_daily.append(puzzle.to_dict())
        quality = policy.evaluate_seed_scores(ref)
        report["planned"].append(
            {
                "date": puzzle.date.isoformat(),
                "pair_id": puzzle.pair_id,
                "ref_version": puzzle.ref_version,
                "model_version": ref.model_version,
                "spread": quality.spread,
                "p50": quality.p50,
                "frozen_at": puzzle.frozen_at.isoformat(),
            }
        )

    merged_payload = {
        "daily_puzzles": sorted(merged_daily, key=lambda item: item["date"])
    }
    if report["errors"]:
        report["applied"] = False
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "merged_daily_puzzles.json", merged_payload)
    write_json(out_dir / "daily_puzzle_plan.json", report)
    (out_dir / "daily_puzzle_plan.md").write_text(render_markdown(report), encoding="utf-8")
    if apply and not report["errors"]:
        write_json(daily_puzzles_path, merged_payload)
    return report


def next_daily_date(existing: list[DailyPuzzle]) -> date:
    if not existing:
        return date.today()
    return max(item.date for item in existing) + timedelta(days=1)


def skip_ref(ref: SeedScoreRef, reason: str) -> dict[str, Any]:
    return {
        "ref_version": ref.ref_version,
        "pair_id": ref.pair_id,
        "model_version": ref.model_version,
        "reason": reason,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DailyPuzzle plan",
        "",
        f"- applied: `{str(report['applied']).lower()}`",
        f"- start_date: `{report['start_date']}`",
        f"- days: `{report['days']}`",
        f"- planned: `{len(report['planned'])}`",
        f"- skipped: `{len(report['skipped'])}`",
        f"- errors: `{len(report['errors'])}`",
        "",
        "## Planned",
        "",
        "| date | pair_id | ref_version | model | spread | p50 |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for item in report["planned"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["date"],
                    item["pair_id"],
                    item["ref_version"],
                    item["model_version"],
                    f"{item['spread']:.4f}",
                    f"{item['p50']:.4f}",
                ]
            )
            + " |"
        )
    if report["skipped"]:
        lines.extend(["", "## Skipped", "", "| ref_version | pair_id | reason |", "| --- | --- | --- |"])
        for item in report["skipped"]:
            lines.append(f"| {item['ref_version']} | {item['pair_id']} | {item['reason']} |")
    if report["errors"]:
        lines.extend(["", "## Errors", "", "| kind | id | detail |", "| --- | --- | --- |"])
        for item in report["errors"]:
            identifier = item.get("date") or item.get("ref_version") or item.get("pair_id") or "-"
            lines.append(f"| {item['kind']} | {identifier} | {item['detail']} |")
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
