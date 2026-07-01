from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import ssl
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_app_store_connect import build_jwt, parse_env_file  # noqa: E402
from tools.create_app_store_records import api_error_detail, api_request, find_app  # noqa: E402


DEFAULT_ENV = ROOT / ".env.appstore"
DEFAULT_OUT_DIR = ROOT / "reports" / "testflight_review"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit TestFlight and App Review readiness.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = audit_testflight_review_readiness(args.env_file, args.out_dir)
    print(f"Wrote {args.out_dir / 'testflight_review_readiness.json'}")
    print(f"Wrote {args.out_dir / 'testflight_review_readiness.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def audit_testflight_review_readiness(env_file: Path, out_dir: Path) -> dict[str, Any]:
    env = parse_env_file(env_file)
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    token = ""
    app: dict[str, Any] | None = None
    private_key = Path(env.get("ASC_PRIVATE_KEY_PATH", ""))
    if private_key and not private_key.is_absolute():
        private_key = (env_file.parent / private_key).resolve()

    required = ["ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_PATH", "ASC_BUNDLE_ID"]
    missing = [key for key in required if not env.get(key)]
    add_check(checks, errors, "appstore_credentials_present", not missing, "all keys present" if not missing else f"missing={missing}")
    add_check(checks, errors, "private_key_exists", private_key.exists(), redact_path(private_key))
    if not missing and private_key.exists():
        token = build_jwt(env["ASC_KEY_ID"], env["ASC_ISSUER_ID"], private_key)
        add_check(checks, errors, "jwt_generated", True, "ES256 token generated")

    if token:
        app = find_app(token, env["ASC_BUNDLE_ID"])
    add_check(checks, errors, "app_record_found", bool(app), f"app_id={app.get('id', '') if app else ''}")

    versions: list[dict[str, Any]] = []
    builds: list[dict[str, Any]] = []
    beta_groups: list[dict[str, Any]] = []
    if token and app:
        versions = get_data(token, f"/v1/apps/{app['id']}/appStoreVersions", {"limit": "5"})
        builds = get_data(token, f"/v1/apps/{app['id']}/builds", {"limit": "10"})
        beta_groups = get_data(token, f"/v1/apps/{app['id']}/betaGroups", {"limit": "50"})

    current_version = versions[0] if versions else None
    version_attrs = current_version.get("attributes", {}) if current_version else {}
    add_check(
        checks,
        errors,
        "app_store_version_prepare_for_submission",
        version_attrs.get("appStoreState") == "PREPARE_FOR_SUBMISSION",
        json.dumps(
            {
                "version": version_attrs.get("versionString", ""),
                "state": version_attrs.get("appStoreState", ""),
                "releaseType": version_attrs.get("releaseType", ""),
                "usesIdfa": version_attrs.get("usesIdfa"),
            },
            sort_keys=True,
        ),
    )
    add_check(checks, errors, "testflight_build_uploaded", bool(builds), f"build_count={len(builds)}")

    internal_groups = [
        group
        for group in beta_groups
        if group.get("attributes", {}).get("isInternalGroup")
    ]
    add_check(
        checks,
        errors,
        "internal_beta_group_ready",
        bool(internal_groups),
        f"group_count={len(internal_groups)}",
    )

    app_store_audit = load_json(ROOT / "reports" / "app_store" / "app_store_release.json")
    add_check(
        checks,
        errors,
        "app_store_release_kit_valid",
        bool(app_store_audit.get("valid")),
        f"passed={app_store_audit.get('summary', {}).get('passed_checks', 0)} failed={app_store_audit.get('summary', {}).get('failed_checks', 0)}",
    )

    metadata_sync = load_json(ROOT / "reports" / "app_store_connect" / "app_store_metadata_sync.json")
    add_check(
        checks,
        errors,
        "app_store_metadata_synced",
        bool(metadata_sync.get("valid")),
        f"actions={metadata_sync.get('summary', {}).get('actions', 0)}",
    )

    screenshots = sorted((ROOT / "reports" / "app_store" / "screenshots" / "generated" / "iphone-6.9").glob("*.png"))
    add_check(checks, errors, "app_store_screenshots_generated", len(screenshots) >= 5, f"count={len(screenshots)}")

    api_base = env.get("GITAI_IOS_API_BASE", "")
    api_health = check_api(api_base)
    add_check(checks, errors, "production_api_reachable", api_health["ok"], api_health["detail"])

    archive = ROOT / "build" / "ios" / "archive" / "gitai.xcarchive"
    add_check(checks, errors, "xcode_archive_exists", archive.exists(), str(archive))
    if not archive.exists():
        warnings.append("Run tools/archive_ios_testflight.sh from a normal local terminal with Xcode signing access.")
    if not api_health["ok"]:
        warnings.append("Production API must be live before App Review. The iOS bundle currently points at GITAI_IOS_API_BASE.")
    if not builds:
        warnings.append("No TestFlight build is uploaded yet.")

    report = {
        "valid": not errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "app_id": app.get("id", "") if app else "",
            "bundle_id": env.get("ASC_BUNDLE_ID", ""),
            "app_store_version_id": current_version.get("id", "") if current_version else "",
            "app_store_version": version_attrs.get("versionString", ""),
            "app_store_state": version_attrs.get("appStoreState", ""),
            "build_count": len(builds),
            "internal_beta_group_count": len(internal_groups),
            "screenshot_count": len(screenshots),
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
        },
    }
    write_report(out_dir, report)
    return report


def get_data(token: str, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
    try:
        payload = api_request(token, "GET", path, params=params)
    except HTTPError as exc:
        return [{"attributes": {"error": api_error_detail(exc)}}]
    data = payload.get("data", [])
    return data if isinstance(data, list) else []


def check_api(api_base: str) -> dict[str, Any]:
    if not api_base.startswith("https://"):
        return {"ok": False, "detail": f"not_https={api_base}"}
    host = api_base.removeprefix("https://").split("/", 1)[0].split(":", 1)[0]
    try:
        socket.getaddrinfo(host, 443)
    except socket.gaierror:
        return {"ok": False, "detail": f"dns_unresolved={host}"}
    try:
        request = Request(f"{api_base.rstrip('/')}/healthz")
        context = ssl.create_default_context()
        with urlopen(request, timeout=15, context=context) as response:
            return {"ok": 200 <= response.status < 300, "detail": f"healthz_status={response.status}"}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "detail": type(exc).__name__}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def redact_path(path: Path) -> str:
    parts = path.parts
    if ".secrets" in parts:
        index = parts.index(".secrets")
        return str(Path(*parts[: index + 1]) / "..." / path.name)
    return str(path)


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "testflight_review_readiness.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "testflight_review_readiness.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# TestFlight / App Review Readiness",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- app_id: `{summary.get('app_id', '')}`",
        f"- bundle_id: `{summary.get('bundle_id', '')}`",
        f"- app_store_version: `{summary.get('app_store_version', '')}`",
        f"- app_store_state: `{summary.get('app_store_state', '')}`",
        f"- build_count: `{summary.get('build_count', 0)}`",
        f"- internal_beta_group_count: `{summary.get('internal_beta_group_count', 0)}`",
        f"- screenshot_count: `{summary.get('screenshot_count', 0)}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        "",
        "## Checks",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
