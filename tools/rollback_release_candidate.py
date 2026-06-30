from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPLY_REPORT = ROOT / "reports" / "release_candidate_apply" / "apply_release_candidate.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "release_candidate_rollback"


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback a gitai release candidate from its apply report backups.")
    parser.add_argument("--apply-report", type=Path, default=DEFAULT_APPLY_REPORT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = rollback_release_candidate(
        apply_report_path=args.apply_report,
        out_dir=args.out_dir,
        apply=args.apply,
    )
    print(f"Wrote {args.out_dir / 'rollback_release_candidate.json'}")
    print(f"Wrote {args.out_dir / 'rollback_release_candidate.md'}")
    print(f"valid={str(report['valid']).lower()} rolled_back={str(report['rolled_back']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def rollback_release_candidate(
    apply_report_path: Path,
    out_dir: Path,
    apply: bool = False,
) -> dict[str, Any]:
    apply_report = load_json(apply_report_path)
    report: dict[str, Any] = {
        "valid": False,
        "requested_apply": apply,
        "rolled_back": False,
        "apply_report": str(apply_report_path),
        "files": [],
        "seed_ghost_images": [],
        "errors": [],
        "warnings": [],
    }
    if not apply_report.get("applied", False):
        report["errors"].append("apply report was not applied; nothing can be rolled back")
        return write_rollback_report(out_dir, report)

    file_plan = rollback_plan(apply_report.get("files", []), remove_missing_backups=False)
    image_plan = rollback_plan(apply_report.get("seed_ghost_images", []), remove_missing_backups=True)
    report["files"] = render_plan(file_plan, apply=apply)
    report["seed_ghost_images"] = render_plan(image_plan, apply=apply)

    for item in [*file_plan, *image_plan]:
        if item["action"] == "missing_backup":
            report["errors"].append(f"missing backup for {item['target']}")
        elif item["action"] == "missing_target_for_removal":
            report["warnings"].append(f"target already absent: {item['target']}")

    if report["errors"]:
        return write_rollback_report(out_dir, report)
    report["valid"] = True
    if not apply:
        return write_rollback_report(out_dir, report)

    for index, item in enumerate(file_plan):
        perform_rollback_action(item)
        report["files"][index]["status"] = applied_status(item)
    for index, item in enumerate(image_plan):
        perform_rollback_action(item)
        report["seed_ghost_images"][index]["status"] = applied_status(item)
    report["rolled_back"] = True
    return write_rollback_report(out_dir, report)


def rollback_plan(items: list[dict[str, Any]], remove_missing_backups: bool) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in items:
        target = Path(str(item.get("target", "")))
        backup_value = str(item.get("backup", ""))
        backup = Path(backup_value) if backup_value else None
        if backup is not None and backup.exists():
            action = "restore"
        elif remove_missing_backups:
            action = "remove" if target.exists() else "missing_target_for_removal"
        else:
            action = "missing_backup"
        plan.append(
            {
                "target": target,
                "backup": backup,
                "action": action,
            }
        )
    return plan


def render_plan(plan: list[dict[str, Any]], apply: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in plan:
        action = str(item["action"])
        if action == "restore":
            status = "pending_restore" if apply else "would_restore"
        elif action == "remove":
            status = "pending_remove" if apply else "would_remove"
        elif action == "missing_target_for_removal":
            status = "already_absent"
        else:
            status = "missing_backup"
        rows.append(
            {
                "target": str(item["target"]),
                "backup": str(item["backup"]) if item["backup"] else "",
                "status": status,
            }
        )
    return rows


def perform_rollback_action(item: dict[str, Any]) -> None:
    target = item["target"]
    backup = item["backup"]
    action = item["action"]
    if action == "restore":
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
    elif action == "remove" and target.exists():
        target.unlink()


def applied_status(item: dict[str, Any]) -> str:
    if item["action"] == "restore":
        return "restored"
    if item["action"] in {"remove", "missing_target_for_removal"}:
        return "removed" if item["action"] == "remove" else "already_absent"
    return "missing_backup"


def write_rollback_report(out_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "rollback_release_candidate.json", report)
    (out_dir / "rollback_release_candidate.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Rollback release candidate",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- requested_apply: `{str(report['requested_apply']).lower()}`",
        f"- rolled_back: `{str(report['rolled_back']).lower()}`",
        f"- apply_report: `{report['apply_report']}`",
        "",
        "## Files",
        "",
        "| target | backup | status |",
        "| --- | --- | --- |",
    ]
    for item in report["files"]:
        lines.append(f"| {item['target']} | {item['backup']} | {item['status']} |")
    lines.extend(["", "## Seed Ghost Images", "", "| target | backup | status |", "| --- | --- | --- |"])
    for item in report["seed_ghost_images"]:
        lines.append(f"| {item['target']} | {item['backup']} | {item['status']} |")
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
