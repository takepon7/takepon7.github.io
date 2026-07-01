from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "app_store"
SCREENSHOT_DIR = ROOT / "reports" / "app_store" / "screenshots" / "generated" / "iphone-6.9"
EXPECTED_SCREENSHOT_SIZE = (1290, 2796)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit App Store release kit readiness.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = audit_app_store_release(args.out_dir)
    print(f"Wrote {args.out_dir / 'app_store_release.json'}")
    print(f"Wrote {args.out_dir / 'app_store_release.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def audit_app_store_release(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    required_docs = {
        "release_plan": ROOT / "docs" / "release" / "app_store_release_plan.md",
        "metadata_ja": ROOT / "docs" / "release" / "app_store_metadata_ja.md",
        "connect_api_notes": ROOT / "docs" / "release" / "app_store_connect_api.md",
        "env_template": ROOT / ".env.appstore.example",
    }
    for name, path in required_docs.items():
        add_check(checks, errors, f"{name}_exists", path.exists(), str(path))

    metadata_text = required_docs["metadata_ja"].read_text(encoding="utf-8") if required_docs["metadata_ja"].exists() else ""
    required_metadata_tokens = [
        "Name:",
        "Subtitle:",
        "Description",
        "Keywords",
        "Review Notes",
        "Privacy Policy URL",
        "No paid purchase is required for review.",
    ]
    missing_metadata_tokens = [token for token in required_metadata_tokens if token not in metadata_text]
    add_check(
        checks,
        errors,
        "metadata_required_fields_ready",
        not missing_metadata_tokens,
        "all metadata sections present" if not missing_metadata_tokens else f"missing={missing_metadata_tokens}",
    )

    env_text = required_docs["env_template"].read_text(encoding="utf-8") if required_docs["env_template"].exists() else ""
    required_env_keys = [
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY_PATH",
        "ASC_BUNDLE_ID",
        "ASC_APP_SKU",
        "GITAI_IOS_API_BASE",
        "GITAI_IOS_SUPPORT_URL",
        "GITAI_IOS_MARKETING_URL",
        "GITAI_IOS_PRIVACY_URL",
    ]
    missing_env_keys = [key for key in required_env_keys if not re.search(rf"^{key}=", env_text, re.M)]
    add_check(
        checks,
        errors,
        "appstore_env_template_ready",
        not missing_env_keys,
        "all App Store env keys present" if not missing_env_keys else f"missing={missing_env_keys}",
    )

    web_assets = {
        "app_icon_1024_source": ROOT / "web" / "public" / "brand" / "gitai-app-icon-source.png",
        "og_image": ROOT / "web" / "public" / "brand" / "og-image.png",
        "marketing_hero": ROOT / "web" / "public" / "brand" / "marketing-hero-16x9.png",
    }
    missing_assets = [name for name, path in web_assets.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "store_visual_assets_ready",
        not missing_assets,
        "icon source, og image, and hero are present" if not missing_assets else f"missing={missing_assets}",
    )

    screenshots = sorted(SCREENSHOT_DIR.glob("*.png"))
    screenshot_results = []
    for path in screenshots:
        with Image.open(path) as image:
            screenshot_results.append(
                {
                    "path": str(path),
                    "size": image.size,
                    "ok": image.size == EXPECTED_SCREENSHOT_SIZE,
                }
            )
    add_check(
        checks,
        errors,
        "iphone_6_9_screenshots_ready",
        len(screenshot_results) >= 5 and all(item["ok"] for item in screenshot_results),
        json.dumps(
            {
                "count": len(screenshot_results),
                "expected_size": EXPECTED_SCREENSHOT_SIZE,
                "bad": [item for item in screenshot_results if not item["ok"]],
            },
            sort_keys=True,
        ),
    )

    launch_audit = load_json(ROOT / "reports" / "launch_package_audit" / "launch_package_audit.json")
    add_check(
        checks,
        errors,
        "web_launch_package_valid",
        bool(launch_audit.get("valid")),
        f"passed={launch_audit.get('summary', {}).get('passed_checks', 0)} "
        f"failed={launch_audit.get('summary', {}).get('failed_checks', 0)}",
    )

    report = {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "screenshots": screenshot_results,
        "manual_followups": [
            "Create the App Store Connect app record and reserve the final bundle ID.",
            "Build the iOS wrapper with the final production API origin.",
            "Upload an archive build and run TestFlight first-play QA.",
            "Attach generated screenshots and submit with manual release.",
        ],
        "summary": {
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "screenshot_count": len(screenshot_results),
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


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app_store_release.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "app_store_release.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# App Store Release Audit",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        f"- screenshot_count: `{summary['screenshot_count']}`",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["screenshots"]:
        lines.extend(["", "## Screenshots", ""])
        for item in report["screenshots"]:
            lines.append(f"- `{item['path']}`: `{item['size'][0]}x{item['size'][1]}`")
    if report["manual_followups"]:
        lines.extend(["", "## Manual Follow-ups", ""])
        lines.extend(f"- {item}" for item in report["manual_followups"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
