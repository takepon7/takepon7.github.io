from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from typing import Iterator

from fastapi.testclient import TestClient
from PIL import Image

from gitai_phase0.api import build_state_from_env, create_app


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

    legal_pages = {
        "privacy": (web_dist_dir / "privacy.html", ["Privacy Policy", "取得する情報", "削除"]),
        "terms": (web_dist_dir / "terms.html", ["Terms of Use", "禁止事項", "投稿コンテンツ"]),
        "safety": (web_dist_dir / "safety.html", ["Safety Guidelines", "不正対策", "共有時の注意"]),
    }
    legal_results = validate_text_pages(legal_pages)
    legal_links = [token for token in ("/privacy.html", "/terms.html", "/safety.html") if token in js_text]
    add_check(
        checks,
        errors,
        "public_policy_pages_ready",
        all(item["ok"] for item in legal_results.values()) and len(legal_links) == 3,
        json.dumps({"pages": legal_results, "linked_from_app": legal_links}, sort_keys=True),
    )

    same_origin = validate_same_origin_static_serving(web_dist_dir)
    add_check(
        checks,
        errors,
        "same_origin_web_serving_ready",
        same_origin["ok"],
        json.dumps(same_origin, sort_keys=True),
    )

    container = validate_container_files()
    add_check(
        checks,
        errors,
        "container_deploy_files_ready",
        container["ok"],
        json.dumps(container, sort_keys=True),
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


def validate_text_pages(expected: dict[str, tuple[Path, list[str]]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, (path, tokens) in expected.items():
        if not path.exists():
            results[name] = {"ok": False, "path": str(path), "missing": tokens}
            continue
        text = path.read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in text]
        results[name] = {"ok": not missing, "path": str(path), "missing": missing}
    return results


def validate_same_origin_static_serving(web_dist_dir: Path) -> dict[str, Any]:
    if not (web_dist_dir / "index.html").exists():
        return {"ok": False, "error": f"missing web dist index: {web_dist_dir / 'index.html'}"}
    with tempfile.TemporaryDirectory(prefix="gitai-public-launch-") as tmpdir:
        tmp = Path(tmpdir)
        env = {
            "GITAI_STATIC_DIR": str(web_dist_dir),
            "GITAI_RUNTIME_DB": str(tmp / "runtime.sqlite"),
            "GITAI_IMAGE_STORE": str(tmp / "submissions"),
            "GITAI_MODEL": "heuristic",
            "GITAI_OCR": "fingerprint",
            "GITAI_MODERATION": "fingerprint",
            "GITAI_TODAY": "2026-07-06",
            "GITAI_LAYER2_ACTOR": "null",
        }
        with patched_env(env, remove=("GITAI_DAILY_REF_VERSION", "GITAI_SEASON_MODEL_VERSION")):
            client = TestClient(create_app(build_state_from_env()))
            app_shell = client.get("/")
            privacy = client.get("/privacy.html")
            api = client.get("/v1/daily-puzzle")
        return {
            "ok": (
                app_shell.status_code == 200
                and '<div id="app"></div>' in app_shell.text
                and "default-src 'self'" in app_shell.headers.get("content-security-policy", "")
                and "object-src 'none'" in app_shell.headers.get("content-security-policy", "")
                and privacy.status_code == 200
                and "Privacy Policy" in privacy.text
                and api.status_code == 200
                and api.json().get("pair_id") == "apple_to_baseball"
            ),
            "app_status": app_shell.status_code,
            "privacy_status": privacy.status_code,
            "api_status": api.status_code,
            "api_pair_id": api.json().get("pair_id") if api.status_code == 200 else "",
            "csp": app_shell.headers.get("content-security-policy", ""),
        }


def validate_container_files() -> dict[str, Any]:
    dockerfile = ROOT / "Dockerfile"
    dockerignore = ROOT / ".dockerignore"
    if not dockerfile.exists() or not dockerignore.exists():
        return {
            "ok": False,
            "missing": [str(path) for path in (dockerfile, dockerignore) if not path.exists()],
        }
    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    dockerignore_text = dockerignore.read_text(encoding="utf-8")
    required_dockerfile_tokens = [
        "FROM node:22-bookworm-slim AS web-build",
        "npm ci && npm run build",
        "FROM python:3.10-slim AS runtime",
        "GITAI_STATIC_DIR=/app/web/dist",
        'pip install --no-cache-dir -e ".[api]"',
        "USER gitai",
        '"uvicorn"',
        '"gitai_phase0.server:app"',
    ]
    required_ignore_tokens = ["node_modules/", ".git-local/", ".venv310/", "reports/", "web/dist/"]
    missing = [token for token in required_dockerfile_tokens if token not in dockerfile_text]
    missing_ignore = [token for token in required_ignore_tokens if token not in dockerignore_text]
    return {
        "ok": not missing and not missing_ignore,
        "dockerfile": str(dockerfile),
        "dockerignore": str(dockerignore),
        "missing_dockerfile_tokens": missing,
        "missing_dockerignore_tokens": missing_ignore,
    }


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


@contextmanager
def patched_env(updates: dict[str, str], remove: tuple[str, ...] = ()) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in [*updates.keys(), *remove]}
    for key in remove:
        os.environ.pop(key, None)
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
