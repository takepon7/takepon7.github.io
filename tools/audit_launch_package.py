from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "launch_package_audit"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the publishable web app and marketing launch package.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = audit_launch_package(out_dir=args.out_dir)
    print(f"Wrote {args.out_dir / 'launch_package_audit.json'}")
    print(f"Wrote {args.out_dir / 'launch_package_audit.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def audit_launch_package(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    release = load_json(ROOT / "reports" / "release_readiness" / "release_readiness.json")
    public_launch = load_json(ROOT / "reports" / "public_launch" / "public_launch.json")
    first_play = load_json(ROOT / "reports" / "first_play_api" / "first_play_api.json")
    phase3_static = load_json(ROOT / "reports" / "phase3_static_smoke.json")

    add_check(
        checks,
        errors,
        "release_readiness_valid",
        bool(release.get("valid")) and release.get("summary", {}).get("failed_checks") == 0,
        f"passed={release.get('summary', {}).get('passed_checks', 0)} failed={release.get('summary', {}).get('failed_checks', 0)}",
    )
    add_check(
        checks,
        errors,
        "public_launch_valid",
        bool(public_launch.get("valid")) and public_launch.get("summary", {}).get("failed_checks") == 0,
        f"passed={public_launch.get('summary', {}).get('passed_checks', 0)} failed={public_launch.get('summary', {}).get('failed_checks', 0)}",
    )
    add_check(
        checks,
        errors,
        "first_play_flow_valid",
        bool(first_play.get("valid")) and first_play.get("summary", {}).get("failed_checks") == 0,
        f"passed={first_play.get('summary', {}).get('passed_checks', 0)} failed={first_play.get('summary', {}).get('failed_checks', 0)}",
    )
    add_check(
        checks,
        errors,
        "static_surface_valid",
        bool(phase3_static.get("checks")) and all(bool(value) for value in phase3_static.get("checks", {}).values()),
        f"checks={len(phase3_static.get('checks', {}))}",
    )

    marketing_docs = {
        "marketing_plan": ROOT / "docs" / "marketing" / "marketing_plan.md",
        "asset_manifest": ROOT / "docs" / "marketing" / "asset_manifest.md",
        "launch_copy_kit": ROOT / "docs" / "marketing" / "launch_copy_kit.md",
        "press_one_pager": ROOT / "docs" / "marketing" / "press_one_pager.md",
        "deployment_notes": ROOT / "docs" / "deployment.md",
    }
    missing_docs = [name for name, path in marketing_docs.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "marketing_docs_ready",
        not missing_docs,
        "all launch docs exist" if not missing_docs else f"missing={missing_docs}",
    )

    playtest_docs = {
        "closed_playtest_plan": ROOT / "docs" / "playtest" / "closed_playtest_plan.md",
        "tester_invite": ROOT / "docs" / "playtest" / "tester_invite.md",
        "feedback_form": ROOT / "docs" / "playtest" / "feedback_form.md",
    }
    missing_playtest_docs = [name for name, path in playtest_docs.items() if not path.exists()]
    playtest_text = "\n".join(path.read_text(encoding="utf-8") for path in playtest_docs.values() if path.exists())
    playtest_tokens = [
        "20-50 outside testers",
        "First submission completion rate",
        "Bug feedback is below 20%",
        "テストURL",
        "Did you complete a first submission?",
    ]
    missing_playtest_tokens = [token for token in playtest_tokens if token not in playtest_text]
    add_check(
        checks,
        errors,
        "closed_playtest_kit_ready",
        not missing_playtest_docs and not missing_playtest_tokens,
        json.dumps(
            {
                "missing_docs": missing_playtest_docs,
                "missing_tokens": missing_playtest_tokens,
            },
            sort_keys=True,
        ),
    )

    required_assets = {
        "og_image": ROOT / "web" / "public" / "brand" / "og-image.png",
        "marketing_hero": ROOT / "web" / "public" / "brand" / "marketing-hero-16x9.png",
        "social_feed_square": ROOT / "web" / "public" / "brand" / "social-feed-square.png",
        "social_story_vertical": ROOT / "web" / "public" / "brand" / "social-story-vertical.png",
        "app_icon_192": ROOT / "web" / "public" / "brand" / "app-icon-192.png",
        "app_icon_512": ROOT / "web" / "public" / "brand" / "app-icon-512.png",
        "apple_touch_icon": ROOT / "web" / "public" / "brand" / "apple-touch-icon.png",
        "favicon": ROOT / "web" / "public" / "brand" / "favicon-32.png",
        "share_card_examples": ROOT / "web" / "public" / "brand" / "share-card-examples.json",
    }
    missing_assets = [name for name, path in required_assets.items() if not path.exists()]
    share_card_manifest = load_json(required_assets["share_card_examples"])
    share_cards = list(share_card_manifest.get("examples", []))
    missing_share_cards = [
        item.get("path", "")
        for item in share_cards
        if item.get("path") and not public_asset_path(str(item["path"])).exists()
    ]
    add_check(
        checks,
        errors,
        "imagegen_assets_ready",
        not missing_assets and len(share_cards) >= 5 and not missing_share_cards,
        json.dumps(
            {
                "missing_assets": missing_assets,
                "share_card_examples": len(share_cards),
                "missing_share_cards": missing_share_cards,
            },
            sort_keys=True,
        ),
    )

    policy_pages = {
        "privacy": ROOT / "web" / "public" / "privacy.html",
        "terms": ROOT / "web" / "public" / "terms.html",
        "safety": ROOT / "web" / "public" / "safety.html",
    }
    missing_policy_pages = [name for name, path in policy_pages.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "policy_pages_ready",
        not missing_policy_pages,
        "privacy, terms, and safety pages exist" if not missing_policy_pages else f"missing={missing_policy_pages}",
    )

    manual_followups = [
        "Set production GITAI_CORS_ORIGINS and GITAI_PUBLIC_WEB_URL to the final public origin.",
        "Run an external closed playtest with at least 20 outside players.",
        "Replace or expand heuristic playtest pairs with broader real-model measured pairs before a serious campaign.",
    ]
    report = {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "manual_followups": manual_followups,
        "summary": {
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "manual_followups": len(manual_followups),
            "latest_date": release.get("summary", {}).get("latest_date", ""),
            "latest_pair_id": release.get("summary", {}).get("latest_pair_id", ""),
            "first_play_submission_id": first_play.get("summary", {}).get("submission_id", ""),
        },
    }
    write_report(out_dir, report)
    return report


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def public_asset_path(value: str) -> Path:
    cleaned = value.lstrip("/")
    if cleaned.startswith("web/public/"):
        return ROOT / cleaned
    return ROOT / "web" / "public" / cleaned


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "launch_package_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "launch_package_audit.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Launch Package Audit",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- latest_date: `{summary.get('latest_date', '')}`",
        f"- latest_pair_id: `{summary.get('latest_pair_id', '')}`",
        f"- first_play_submission_id: `{summary.get('first_play_submission_id', '')}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        f"- manual_followups: `{summary['manual_followups']}`",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {item['name']} | {item['status']} | {item['detail']} |"
        for item in report["checks"]
    )
    if report["manual_followups"]:
        lines.extend(["", "## Manual Follow-ups", ""])
        lines.extend(f"- {item}" for item in report["manual_followups"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
