from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "public_launch"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the public web launch readiness smoke for gitai.")
    parser.add_argument("--web-dist", type=Path, default=ROOT / "web" / "dist")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    report = smoke_public_launch(web_dist_dir=args.web_dist, out_dir=args.out_dir)
    print(f"Wrote {args.out_dir / 'public_launch.json'}")
    print(f"Wrote {args.out_dir / 'public_launch.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def smoke_public_launch(
    web_dist_dir: Path = ROOT / "web" / "dist",
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    index = web_dist_dir / "index.html"
    add_check(checks, errors, "web_dist_index_exists", index.exists(), str(index))
    html = index.read_text(encoding="utf-8") if index.exists() else ""

    required_html = {
        "title": "gitai - AIをだます擬態ドローイングゲーム",
        "description": 'name="description"',
        "og_title": 'property="og:title"',
        "og_image": "/brand/og-image.png",
        "twitter_card": 'name="twitter:card"',
        "manifest": "/site.webmanifest",
        "favicon": "/brand/favicon-32.png",
        "apple_touch_icon": "/brand/apple-touch-icon.png",
    }
    missing_html = [name for name, token in required_html.items() if token not in html]
    add_check(
        checks,
        errors,
        "publish_metadata_present",
        not missing_html,
        "all metadata present" if not missing_html else f"missing: {missing_html}",
    )

    js_text = read_built_js(web_dist_dir, html)
    localhost_tokens = [token for token in ("http://127.0.0.1:8000", "http://localhost:8000") if token in js_text]
    add_check(
        checks,
        errors,
        "production_api_not_localhost",
        not localhost_tokens,
        "production bundle uses same-origin/explicit API base"
        if not localhost_tokens
        else f"found: {localhost_tokens}",
    )

    expected_images = {
        "og_image": (web_dist_dir / "brand" / "og-image.png", (1200, 630)),
        "marketing_hero": (web_dist_dir / "brand" / "marketing-hero-16x9.png", (1600, 900)),
        "social_feed_square": (web_dist_dir / "brand" / "social-feed-square.png", (1080, 1080)),
        "social_story_vertical": (web_dist_dir / "brand" / "social-story-vertical.png", (1080, 1920)),
        "app_icon_512": (web_dist_dir / "brand" / "app-icon-512.png", (512, 512)),
        "app_icon_192": (web_dist_dir / "brand" / "app-icon-192.png", (192, 192)),
        "apple_touch_icon": (web_dist_dir / "brand" / "apple-touch-icon.png", (180, 180)),
        "favicon": (web_dist_dir / "brand" / "favicon-32.png", (32, 32)),
    }
    image_results = validate_images(expected_images)
    add_check(
        checks,
        errors,
        "brand_images_have_expected_sizes",
        all(item["ok"] for item in image_results.values()),
        json.dumps(image_results, sort_keys=True),
    )

    manifest_path = web_dist_dir / "site.webmanifest"
    manifest = load_json(manifest_path)
    manifest_ok = (
        manifest.get("name") == "gitai"
        and manifest.get("display") == "standalone"
        and any(item.get("sizes") == "512x512" for item in manifest.get("icons", []))
        and any(item.get("sizes") == "192x192" for item in manifest.get("icons", []))
    )
    add_check(
        checks,
        errors,
        "pwa_manifest_ready",
        manifest_ok,
        "manifest includes standalone app metadata and install icons",
    )

    docs = {
        "marketing_plan": ROOT / "docs" / "marketing" / "marketing_plan.md",
        "asset_manifest": ROOT / "docs" / "marketing" / "asset_manifest.md",
        "launch_copy_kit": ROOT / "docs" / "marketing" / "launch_copy_kit.md",
        "press_one_pager": ROOT / "docs" / "marketing" / "press_one_pager.md",
        "deployment_notes": ROOT / "docs" / "deployment.md",
    }
    missing_docs = [name for name, path in docs.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "launch_docs_exist",
        not missing_docs,
        "marketing, asset, copy, press, and deployment docs exist"
        if not missing_docs
        else f"missing: {missing_docs}",
    )

    readiness = load_json(ROOT / "reports" / "release_readiness" / "release_readiness.json")
    add_check(
        checks,
        errors,
        "release_readiness_valid",
        bool(readiness.get("valid")),
        f"passed={readiness.get('summary', {}).get('passed_checks', 0)} failed={readiness.get('summary', {}).get('failed_checks', 0)}",
    )

    static_smoke = load_json(ROOT / "reports" / "phase3_static_smoke.json")
    failed_static = [name for name, passed in static_smoke.get("checks", {}).items() if not passed]
    add_check(
        checks,
        errors,
        "static_smoke_valid",
        bool(static_smoke.get("checks")) and not failed_static,
        "all static checks pass" if not failed_static else f"failed: {failed_static}",
    )

    warnings.extend(
        [
            "Set real production origins in GITAI_CORS_ORIGINS and GITAI_PUBLIC_WEB_URL before launch.",
            "Run an external closed playtest; the automated smoke cannot prove player fun or acquisition metrics.",
            "Replace heuristic playtest content with broader real-model measured pairs before a serious public campaign.",
        ]
    )
    report = {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "manual_followups": len(warnings),
        },
    }
    write_report(out_dir, report)
    return report


def read_built_js(web_dist_dir: Path, html: str) -> str:
    scripts = re.findall(r'src="([^"]+\.js)"', html)
    return "\n".join(
        (web_dist_dir / script.lstrip("/")).read_text(encoding="utf-8")
        for script in scripts
        if (web_dist_dir / script.lstrip("/")).exists()
    )


def validate_images(expected: dict[str, tuple[Path, tuple[int, int]]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, (path, size) in expected.items():
        if not path.exists():
            results[name] = {"ok": False, "path": str(path), "expected": size, "actual": None}
            continue
        with Image.open(path) as image:
            actual = image.size
        results[name] = {
            "ok": actual == size,
            "path": str(path),
            "expected": size,
            "actual": actual,
        }
    return results


def add_check(
    checks: list[dict[str, str]],
    errors: list[str],
    name: str,
    passed: bool,
    detail: str,
) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "public_launch.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "public_launch.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Public launch smoke",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        f"- manual_followups: `{summary['manual_followups']}`",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["warnings"]:
        lines.extend(["", "## Manual Follow-ups", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
