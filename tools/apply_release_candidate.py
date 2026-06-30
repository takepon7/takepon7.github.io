from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any

try:
    from tools.validate_release_candidate import validate_release_candidate
except ModuleNotFoundError:
    from validate_release_candidate import validate_release_candidate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "release_candidate_apply"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a validated gitai release candidate to canonical data files.")
    parser.add_argument("--promotion-report", type=Path, required=True)
    parser.add_argument("--daily-plan-report", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--seed-scores", type=Path, required=True)
    parser.add_argument("--daily-puzzles", type=Path, required=True)
    parser.add_argument("--seed-ghosts", type=Path, required=True)
    parser.add_argument("--canonical-pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--canonical-seed-scores", type=Path, default=ROOT / "data" / "scoring" / "seed_scores.json")
    parser.add_argument("--canonical-daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--canonical-seed-ghosts", type=Path, default=ROOT / "data" / "competition" / "seed_ghosts.json")
    parser.add_argument(
        "--canonical-seed-ghost-image-dir",
        type=Path,
        default=ROOT / "data" / "competition" / "seed_ghost_images",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--season-id", default="season-1")
    parser.add_argument("--min-planned", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = apply_release_candidate(
        promotion_report_path=args.promotion_report,
        daily_plan_report_path=args.daily_plan_report,
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        daily_puzzles_path=args.daily_puzzles,
        seed_ghosts_path=args.seed_ghosts,
        canonical_pairs_path=args.canonical_pairs,
        canonical_seed_scores_path=args.canonical_seed_scores,
        canonical_daily_puzzles_path=args.canonical_daily_puzzles,
        canonical_seed_ghosts_path=args.canonical_seed_ghosts,
        canonical_seed_ghost_image_dir=args.canonical_seed_ghost_image_dir,
        out_dir=args.out_dir,
        season_id=args.season_id,
        min_planned=args.min_planned,
        apply=args.apply,
    )
    print(f"Wrote {args.out_dir / 'apply_release_candidate.json'}")
    print(f"Wrote {args.out_dir / 'apply_release_candidate.md'}")
    print(f"valid={str(report['valid']).lower()} applied={str(report['applied']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def apply_release_candidate(
    promotion_report_path: Path,
    daily_plan_report_path: Path,
    pairs_path: Path,
    seed_scores_path: Path,
    daily_puzzles_path: Path,
    seed_ghosts_path: Path,
    canonical_pairs_path: Path,
    canonical_seed_scores_path: Path,
    canonical_daily_puzzles_path: Path,
    canonical_seed_ghosts_path: Path,
    canonical_seed_ghost_image_dir: Path,
    out_dir: Path,
    season_id: str = "season-1",
    min_planned: int = 1,
    apply: bool = False,
) -> dict[str, Any]:
    validation = validate_release_candidate(
        promotion_report_path=promotion_report_path,
        daily_plan_report_path=daily_plan_report_path,
        pairs_path=pairs_path,
        seed_scores_path=seed_scores_path,
        daily_puzzles_path=daily_puzzles_path,
        seed_ghosts_path=seed_ghosts_path,
        out_dir=out_dir / "validation",
        season_id=season_id,
        min_planned=min_planned,
    )
    report: dict[str, Any] = {
        "valid": bool(validation["valid"]),
        "applied": False,
        "requested_apply": apply,
        "season_id": season_id,
        "summary": deepcopy(validation["summary"]),
        "files": [],
        "seed_ghost_images": [],
        "errors": [],
        "warnings": apply_warnings(list(validation.get("warnings", [])), apply=apply),
        "validation_report": str(out_dir / "validation" / "release_candidate.json"),
    }
    if not validation["valid"]:
        report["errors"].append("release candidate validation failed")
        return write_apply_report(out_dir, report)

    pairs_payload = load_json(pairs_path)
    seed_scores_payload = load_json(seed_scores_path)
    daily_payload = load_json(daily_puzzles_path)
    seed_ghost_payload = load_json(seed_ghosts_path)
    canonical_seed_ghost_payload, image_copy_plan, copy_errors = build_canonical_seed_ghost_payload(
        seed_ghost_payload=seed_ghost_payload,
        canonical_seed_ghost_image_dir=canonical_seed_ghost_image_dir,
    )
    report["errors"].extend(copy_errors)
    report["seed_ghost_images"] = [
        {
            "source": str(item["source"]),
            "target": str(item["target"]),
            "status": "would_copy" if not apply else "pending",
        }
        for item in image_copy_plan
    ]
    file_plan = [
        {"source": pairs_path, "target": canonical_pairs_path, "payload": pairs_payload},
        {"source": seed_scores_path, "target": canonical_seed_scores_path, "payload": seed_scores_payload},
        {"source": daily_puzzles_path, "target": canonical_daily_puzzles_path, "payload": daily_payload},
        {"source": seed_ghosts_path, "target": canonical_seed_ghosts_path, "payload": canonical_seed_ghost_payload},
    ]
    report["files"] = [
        {
            "source": str(item["source"]),
            "target": str(item["target"]),
            "status": "would_write" if not apply else "pending",
        }
        for item in file_plan
    ]
    if report["errors"]:
        return write_apply_report(out_dir, report)
    if not apply:
        return write_apply_report(out_dir, report)

    backup_dir = out_dir / "backup"
    for index, item in enumerate(file_plan):
        target = item["target"]
        backup_path = backup_file(target, backup_dir)
        write_json(target, item["payload"])
        report["files"][index]["status"] = "written"
        report["files"][index]["backup"] = str(backup_path) if backup_path else ""

    for index, item in enumerate(image_copy_plan):
        source = item["source"]
        target = item["target"]
        backup_path = backup_file(target, backup_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        report["seed_ghost_images"][index]["status"] = "copied"
        report["seed_ghost_images"][index]["backup"] = str(backup_path) if backup_path else ""

    report["applied"] = True
    return write_apply_report(out_dir, report)


def build_canonical_seed_ghost_payload(
    seed_ghost_payload: dict[str, Any],
    canonical_seed_ghost_image_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Path]], list[str]]:
    payload = deepcopy(seed_ghost_payload)
    image_copy_plan: list[dict[str, Path]] = []
    errors: list[str] = []
    for item in payload.get("seed_ghosts", []):
        image_ref = str(item.get("image_ref", ""))
        if not image_ref.startswith("file:"):
            errors.append(f"{item.get('submission_id', '<unknown>')}: image_ref must start with file:")
            continue
        source = resolve_file_ref(image_ref)
        if not source.exists():
            errors.append(f"{item.get('submission_id', '<unknown>')}: image file not found: {source}")
            continue
        target = canonical_seed_ghost_image_dir / source.name
        item["image_ref"] = f"file:{relative_or_absolute(target)}"
        image_copy_plan.append({"source": source, "target": target})
    return payload, image_copy_plan, errors


def resolve_file_ref(image_ref: str) -> Path:
    path = Path(image_ref.removeprefix("file:"))
    return path if path.is_absolute() else ROOT / path


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def backup_file(path: Path, backup_dir: Path) -> Path | None:
    if not path.exists():
        return None
    backup_path = backup_dir / backup_relative_path(path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    return backup_path


def backup_relative_path(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        absolute = path.resolve()
        return Path("absolute") / Path(*absolute.parts[1:])


def write_apply_report(out_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "apply_release_candidate.json", report)
    (out_dir / "apply_release_candidate.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def apply_warnings(validation_warnings: list[str], apply: bool) -> list[str]:
    if not apply:
        return validation_warnings
    replacements = {
        "promotion is a preview; canonical scoring files are not modified": (
            "promotion source was preview; apply wrote merged scoring data to canonical files"
        ),
        "promotion is a preview; validation does not apply canonical scoring files": (
            "promotion source was preview; apply wrote merged scoring data to canonical files"
        ),
        "DailyPuzzle plan is a preview; canonical daily puzzle file is not modified": (
            "DailyPuzzle plan source was preview; apply wrote merged DailyPuzzle data to canonical files"
        ),
        "DailyPuzzle plan is a preview; validation does not apply canonical DailyPuzzle files": (
            "DailyPuzzle plan source was preview; apply wrote merged DailyPuzzle data to canonical files"
        ),
    }
    return [replacements.get(warning, warning) for warning in validation_warnings]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Apply release candidate",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- requested_apply: `{str(report['requested_apply']).lower()}`",
        f"- applied: `{str(report['applied']).lower()}`",
        f"- season_id: `{report['season_id']}`",
        f"- daily_count: `{report['summary'].get('daily_count', 0)}`",
        f"- planned_count: `{report['summary'].get('planned_count', 0)}`",
        f"- seed_ghost_count: `{report['summary'].get('seed_ghost_count', 0)}`",
        "",
        "## Files",
        "",
        "| source | target | status |",
        "| --- | --- | --- |",
    ]
    for item in report["files"]:
        lines.append(f"| {item['source']} | {item['target']} | {item['status']} |")
    lines.extend(["", "## Seed Ghost Images", "", "| source | target | status |", "| --- | --- | --- |"])
    for item in report["seed_ghost_images"]:
        lines.append(f"| {item['source']} | {item['target']} | {item['status']} |")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
