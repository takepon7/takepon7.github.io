from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
from typing import Any

try:
    from tools.validate_phase4_seed_ghosts import build_report as build_seed_ghost_report
except ModuleNotFoundError:
    from validate_phase4_seed_ghosts import build_report as build_seed_ghost_report

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMOTION_REPORT = ROOT / "reports" / "phase2" / "seed_score_promotion" / "promotion_report.json"
DEFAULT_DAILY_PLAN_REPORT = ROOT / "reports" / "phase2" / "daily_puzzle_plan" / "daily_puzzle_plan.json"
DEFAULT_PAIRS = ROOT / "reports" / "phase2" / "seed_score_promotion" / "merged_pairs.json"
DEFAULT_SEED_SCORES = ROOT / "reports" / "phase2" / "seed_score_promotion" / "merged_seed_scores.json"
DEFAULT_DAILY_PUZZLES = ROOT / "reports" / "phase2" / "daily_puzzle_plan" / "merged_daily_puzzles.json"
DEFAULT_SEED_GHOSTS = ROOT / "reports" / "phase4" / "planned_seed_ghosts.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "release_candidate"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a reviewable gitai release candidate bundle.")
    parser.add_argument("--promotion-report", type=Path, default=DEFAULT_PROMOTION_REPORT)
    parser.add_argument("--daily-plan-report", type=Path, default=DEFAULT_DAILY_PLAN_REPORT)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--seed-scores", type=Path, default=DEFAULT_SEED_SCORES)
    parser.add_argument("--daily-puzzles", type=Path, default=DEFAULT_DAILY_PUZZLES)
    parser.add_argument("--seed-ghosts", type=Path, default=DEFAULT_SEED_GHOSTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--season-id", default="season-1")
    parser.add_argument("--min-planned", type=int, default=1)
    args = parser.parse_args()

    report = validate_release_candidate(
        promotion_report_path=args.promotion_report,
        daily_plan_report_path=args.daily_plan_report,
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        daily_puzzles_path=args.daily_puzzles,
        seed_ghosts_path=args.seed_ghosts,
        out_dir=args.out_dir,
        season_id=args.season_id,
        min_planned=args.min_planned,
    )
    print(f"Wrote {args.out_dir / 'release_candidate.json'}")
    print(f"Wrote {args.out_dir / 'release_candidate.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def validate_release_candidate(
    promotion_report_path: Path,
    daily_plan_report_path: Path,
    pairs_path: Path,
    seed_scores_path: Path,
    daily_puzzles_path: Path,
    seed_ghosts_path: Path,
    out_dir: Path,
    season_id: str = "season-1",
    min_planned: int = 1,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "valid": False,
        "season_id": season_id,
        "summary": {},
        "checks": [],
        "errors": [],
        "warnings": [],
        "api_preview_env": {},
    }

    promotion = load_json(promotion_report_path)
    daily_plan = load_json(daily_plan_report_path)
    pairs_payload = load_json(pairs_path)
    seed_scores_payload = load_json(seed_scores_path)
    daily_payload = load_json(daily_puzzles_path)

    checks: list[dict[str, Any]] = report["checks"]
    errors: list[str] = report["errors"]
    warnings: list[str] = report["warnings"]

    add_check(
        checks,
        errors,
        "promotion_has_no_errors",
        not promotion.get("errors"),
        f"{len(promotion.get('errors', []))} promotion errors",
    )
    add_check(
        checks,
        errors,
        "daily_plan_has_no_errors",
        not daily_plan.get("errors"),
        f"{len(daily_plan.get('errors', []))} DailyPuzzle plan errors",
    )
    planned_count = len(daily_plan.get("planned", []))
    add_check(
        checks,
        errors,
        "daily_plan_has_required_new_entries",
        planned_count >= max(0, min_planned),
        f"{planned_count} planned entries, expected at least {max(0, min_planned)}",
    )

    pair_by_id = {str(item.get("pair_id")): item for item in pairs_payload.get("pairs", [])}
    ref_by_version = {
        str(item.get("ref_version")): item for item in seed_scores_payload.get("seed_scores", [])
    }
    daily_entries = list(daily_payload.get("daily_puzzles", []))
    dates = [str(item.get("date")) for item in daily_entries]
    add_check(
        checks,
        errors,
        "daily_dates_are_unique",
        len(dates) == len(set(dates)),
        "DailyPuzzle dates must be unique",
    )

    linkage_errors = release_linkage_errors(daily_entries, pair_by_id, ref_by_version)
    add_check(
        checks,
        errors,
        "daily_entries_reference_known_pairs_and_refs",
        not linkage_errors,
        "; ".join(linkage_errors) if linkage_errors else "all DailyPuzzle entries resolve",
    )

    seed_ghost_report = build_seed_ghost_report(
        daily_puzzles_path=daily_puzzles_path,
        pairs_path=pairs_path,
        seed_ghosts_path=seed_ghosts_path,
        season_id=season_id,
    )
    report["seed_ghost_report"] = asdict(seed_ghost_report)
    add_check(
        checks,
        errors,
        "seed_ghosts_cover_daily_entries",
        seed_ghost_report.valid,
        "; ".join(seed_ghost_report.errors) if seed_ghost_report.errors else "seed ghosts valid",
    )

    if not promotion.get("applied", False):
        warnings.append("promotion is a preview; validation does not apply canonical scoring files")
    if not daily_plan.get("applied", False):
        warnings.append("DailyPuzzle plan is a preview; validation does not apply canonical DailyPuzzle files")

    preview_date = preview_today(daily_plan, daily_entries)
    report["api_preview_env"] = {
        "GITAI_PAIRS_PATH": str(pairs_path),
        "GITAI_SEED_SCORES_PATH": str(seed_scores_path),
        "GITAI_DAILY_PUZZLES_PATH": str(daily_puzzles_path),
        "GITAI_SEED_GHOSTS": str(seed_ghosts_path),
        "GITAI_SEASON_ID": season_id,
        "GITAI_TODAY": preview_date,
    }
    report["summary"] = {
        "pair_count": len(pair_by_id),
        "seed_score_count": len(ref_by_version),
        "daily_count": len(daily_entries),
        "planned_count": planned_count,
        "seed_ghost_count": seed_ghost_report.seed_count,
        "promotion_errors": len(promotion.get("errors", [])),
        "daily_plan_errors": len(daily_plan.get("errors", [])),
        "preview_today": preview_date,
    }
    report["valid"] = not errors

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "release_candidate.json", report)
    (out_dir / "release_candidate.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def release_linkage_errors(
    daily_entries: list[dict[str, Any]],
    pair_by_id: dict[str, dict[str, Any]],
    ref_by_version: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for item in daily_entries:
        puzzle_date = str(item.get("date"))
        pair_id = str(item.get("pair_id"))
        ref_version = str(item.get("ref_version"))
        if pair_id not in pair_by_id:
            errors.append(f"{puzzle_date}: unknown pair_id {pair_id}")
        ref = ref_by_version.get(ref_version)
        if ref is None:
            errors.append(f"{puzzle_date}: unknown ref_version {ref_version}")
        elif str(ref.get("pair_id")) != pair_id:
            errors.append(f"{puzzle_date}: ref pair_id {ref.get('pair_id')} does not match {pair_id}")
    return errors


def preview_today(daily_plan: dict[str, Any], daily_entries: list[dict[str, Any]]) -> str:
    planned = daily_plan.get("planned", [])
    if planned:
        return str(planned[0]["date"])
    dates: list[date] = []
    for item in daily_entries:
        try:
            dates.append(date.fromisoformat(str(item["date"])))
        except (KeyError, ValueError):
            continue
    return max(dates).isoformat() if dates else ""


def add_check(
    checks: list[dict[str, Any]],
    errors: list[str],
    name: str,
    passed: bool,
    detail: str,
) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Release candidate validation",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- season_id: `{report['season_id']}`",
        f"- pair_count: `{report['summary']['pair_count']}`",
        f"- seed_score_count: `{report['summary']['seed_score_count']}`",
        f"- daily_count: `{report['summary']['daily_count']}`",
        f"- planned_count: `{report['summary']['planned_count']}`",
        f"- seed_ghost_count: `{report['summary']['seed_ghost_count']}`",
        f"- preview_today: `{report['summary']['preview_today']}`",
        "",
        "## Checks",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['status']} | {item['detail']} |")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    lines.extend(["", "## API Preview", "", "```bash"])
    for key, value in report["api_preview_env"].items():
        lines.append(f"{key}={quote_shell(str(value))} \\")
    lines.append("npm run dev:api:fast")
    lines.extend(["```", ""])
    return "\n".join(lines)


def quote_shell(value: str) -> str:
    if value and all(char.isalnum() or char in "/._:-" for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
