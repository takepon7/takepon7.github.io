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

    ios_files = {
        "capacitor_config": ROOT / "capacitor.config.ts",
        "xcode_project": ROOT / "ios" / "App" / "App.xcodeproj" / "project.pbxproj",
        "info_plist": ROOT / "ios" / "App" / "App" / "Info.plist",
        "ios_index": ROOT / "ios" / "App" / "App" / "public" / "index.html",
        "ios_native_config": ROOT / "ios" / "App" / "App" / "public" / "native-config.js",
        "ios_app_icon": ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-512@2x.png",
        "ios_splash": ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "Splash.imageset" / "splash-2732x2732.png",
    }
    missing_ios_files = [name for name, path in ios_files.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "ios_wrapper_files_ready",
        not missing_ios_files,
        "Capacitor iOS project exists" if not missing_ios_files else f"missing={missing_ios_files}",
    )
    capacitor_text = ios_files["capacitor_config"].read_text(encoding="utf-8") if ios_files["capacitor_config"].exists() else ""
    add_check(
        checks,
        errors,
        "capacitor_config_ready",
        "app.gitai.game" in capacitor_text and "web/dist" in capacitor_text,
        "appId=app.gitai.game webDir=web/dist",
    )
    ios_public_text = ""
    if ios_files["ios_index"].exists():
        ios_public_text += ios_files["ios_index"].read_text(encoding="utf-8", errors="ignore")
    if ios_files["ios_native_config"].exists():
        ios_public_text += ios_files["ios_native_config"].read_text(encoding="utf-8", errors="ignore")
    for js_path in (ROOT / "ios" / "App" / "App" / "public" / "assets").glob("*.js"):
        ios_public_text += js_path.read_text(encoding="utf-8", errors="ignore")
    add_check(
        checks,
        errors,
        "ios_bundle_api_base_ready",
        "127.0.0.1" not in ios_public_text
        and "localhost" not in ios_public_text
        and "https://api.gitai.game" in ios_public_text,
        "iOS bundle points at https://api.gitai.game",
    )
    ios_icon_ok = image_size(ios_files["ios_app_icon"]) == (1024, 1024)
    ios_splash_ok = image_size(ios_files["ios_splash"]) == (2732, 2732)
    add_check(
        checks,
        errors,
        "ios_native_assets_ready",
        ios_icon_ok and ios_splash_ok,
        json.dumps(
            {
                "app_icon": image_size(ios_files["ios_app_icon"]),
                "splash": image_size(ios_files["ios_splash"]),
            },
            sort_keys=True,
        ),
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

    public_launch = load_json(ROOT / "reports" / "public_launch" / "public_launch.json")
    add_check(
        checks,
        errors,
        "web_public_launch_valid",
        bool(public_launch.get("valid")),
        f"passed={public_launch.get('summary', {}).get('passed_checks', 0)} "
        f"failed={public_launch.get('summary', {}).get('failed_checks', 0)}",
    )

    connect_check = load_json(ROOT / "reports" / "app_store_connect" / "app_store_connect.json")
    add_check(
        checks,
        errors,
        "app_store_connect_record_ready",
        bool(connect_check.get("valid")),
        json.dumps(
            {
                "app_id": connect_check.get("summary", {}).get("app_id", ""),
                "bundle_id": connect_check.get("summary", {}).get("bundle_id", ""),
                "bundle_resource_id": connect_check.get("summary", {}).get("bundle_resource_id", ""),
            },
            sort_keys=True,
        ),
    )

    metadata_sync = load_json(ROOT / "reports" / "app_store_connect" / "app_store_metadata_sync.json")
    metadata_actions = metadata_sync.get("actions", [])
    required_synced_targets = {
        "appInfoLocalization",
        "appStoreVersionLocalization.description",
        "appStoreVersionLocalization.keywords",
        "appStoreVersionLocalization.promotionalText",
        "appStoreVersion",
    }
    synced_targets = {
        str(item.get("target", ""))
        for item in metadata_actions
        if item.get("status") == "updated"
    }
    missing_synced_targets = sorted(required_synced_targets - synced_targets)
    add_check(
        checks,
        errors,
        "app_store_text_metadata_synced",
        bool(metadata_sync.get("valid")) and not missing_synced_targets,
        json.dumps(
            {
                "missing": missing_synced_targets,
                "actions": len(metadata_actions),
            },
            sort_keys=True,
        ),
    )
    url_metadata_synced = any(
        item.get("name") == "url_metadata_synced" and item.get("status") == "pass"
        for item in metadata_sync.get("checks", [])
    )
    add_check(
        checks,
        errors,
        "app_store_url_metadata_synced",
        bool(metadata_sync.get("valid")) and url_metadata_synced,
        "support, marketing, and privacy URLs synced" if url_metadata_synced else "URL metadata not synced",
    )

    report = {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "screenshots": screenshot_results,
        "manual_followups": [
            "Point DNS and hosting for gitai.game and api.gitai.game.",
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


def image_size(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    with Image.open(path) as image:
        return image.size


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
