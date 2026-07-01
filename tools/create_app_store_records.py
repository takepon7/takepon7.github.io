from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import ssl


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_app_store_connect import ASC_API, build_jwt, certifi_where, parse_env_file  # noqa: E402

DEFAULT_ENV = ROOT / ".env.appstore"
DEFAULT_OUT_DIR = ROOT / "reports" / "app_store_connect"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create missing App Store Connect Bundle ID and App records.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--bundle-id-name",
        default="gitai",
        help="Display name for the Apple Developer bundle identifier resource.",
    )
    args = parser.parse_args()
    report = create_app_store_records(args.env_file, args.out_dir, args.bundle_id_name)
    print(f"Wrote {args.out_dir / 'app_store_record_creation.json'}")
    print(f"Wrote {args.out_dir / 'app_store_record_creation.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def create_app_store_records(env_file: Path, out_dir: Path, bundle_id_name: str) -> dict[str, Any]:
    env = parse_env_file(env_file)
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    required = [
        "ASC_KEY_ID",
        "ASC_ISSUER_ID",
        "ASC_PRIVATE_KEY_PATH",
        "ASC_BUNDLE_ID",
        "ASC_APP_SKU",
        "ASC_APP_NAME",
        "ASC_PRIMARY_LOCALE",
    ]
    missing = [key for key in required if not env.get(key)]
    add_check(checks, errors, "required_env_present", not missing, "all keys present" if not missing else f"missing={missing}")
    if missing:
        return write_and_return(out_dir, checks, errors, env, None, None)

    private_key = Path(env["ASC_PRIVATE_KEY_PATH"])
    if not private_key.is_absolute():
        private_key = (env_file.parent / private_key).resolve()
    if not private_key.exists():
        add_check(checks, errors, "private_key_exists", False, "configured private key path does not exist")
        return write_and_return(out_dir, checks, errors, env, None, None)
    add_check(checks, errors, "private_key_exists", True, "private key exists")

    token = build_jwt(env["ASC_KEY_ID"], env["ASC_ISSUER_ID"], private_key)
    add_check(checks, errors, "jwt_generated", True, "ES256 token generated")

    bundle = find_bundle_id(token, env["ASC_BUNDLE_ID"])
    if bundle:
        add_check(checks, errors, "bundle_id_ready", True, f"existing id={bundle.get('id', '')}")
    else:
        try:
            bundle = create_bundle_id(token, env["ASC_BUNDLE_ID"], bundle_id_name)
            add_check(checks, errors, "bundle_id_ready", True, f"created id={bundle.get('id', '')}")
        except HTTPError as exc:
            add_check(checks, errors, "bundle_id_ready", False, api_error_detail(exc))
        except URLError as exc:
            add_check(checks, errors, "bundle_id_ready", False, type(exc.reason).__name__)

    app = find_app(token, env["ASC_BUNDLE_ID"])
    if app:
        add_check(checks, errors, "app_record_ready", True, f"existing id={app.get('id', '')}")
    elif bundle:
        try:
            app = create_app_record(
                token=token,
                bundle_id=env["ASC_BUNDLE_ID"],
                name=env["ASC_APP_NAME"],
                sku=env["ASC_APP_SKU"],
                primary_locale=env["ASC_PRIMARY_LOCALE"],
            )
            add_check(checks, errors, "app_record_ready", True, f"created id={app.get('id', '')}")
        except HTTPError as exc:
            add_check(checks, errors, "app_record_ready", False, api_error_detail(exc))
        except URLError as exc:
            add_check(checks, errors, "app_record_ready", False, type(exc.reason).__name__)
    else:
        add_check(checks, errors, "app_record_ready", False, "skipped because Bundle ID was not ready")

    bundle = find_bundle_id(token, env["ASC_BUNDLE_ID"]) or bundle
    app = find_app(token, env["ASC_BUNDLE_ID"]) or app
    return write_and_return(out_dir, checks, errors, env, bundle, app)


def find_bundle_id(token: str, identifier: str) -> dict[str, Any] | None:
    payload = api_request(
        token,
        "GET",
        "/v1/bundleIds",
        params={"filter[identifier]": identifier, "limit": "1"},
    )
    data = payload.get("data", [])
    return data[0] if isinstance(data, list) and data else None


def create_bundle_id(token: str, identifier: str, name: str) -> dict[str, Any]:
    payload = api_request(
        token,
        "POST",
        "/v1/bundleIds",
        body={
            "data": {
                "type": "bundleIds",
                "attributes": {
                    "identifier": identifier,
                    "name": name,
                    "platform": "IOS",
                },
            }
        },
    )
    return payload["data"]


def find_app(token: str, bundle_id: str) -> dict[str, Any] | None:
    payload = api_request(
        token,
        "GET",
        "/v1/apps",
        params={"filter[bundleId]": bundle_id, "limit": "1"},
    )
    data = payload.get("data", [])
    return data[0] if isinstance(data, list) and data else None


def create_app_record(token: str, bundle_id: str, name: str, sku: str, primary_locale: str) -> dict[str, Any]:
    payload = api_request(
        token,
        "POST",
        "/v1/apps",
        body={
            "data": {
                "type": "apps",
                "attributes": {
                    "bundleId": bundle_id,
                    "name": name,
                    "sku": sku,
                    "primaryLocale": primary_locale,
                },
            }
        },
    )
    return payload["data"]


def api_request(
    token: str,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = urlencode(params or {})
    url = f"{ASC_API}{path}?{query}" if query else f"{ASC_API}{path}"
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    context = ssl.create_default_context(cafile=certifi_where())
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def api_error_detail(exc: HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return f"HTTP {exc.code}"
    errors = payload.get("errors", [])
    if not errors:
        return f"HTTP {exc.code}"
    first = errors[0]
    code = first.get("code", "")
    title = first.get("title", "")
    detail = first.get("detail", "")
    return " ".join(part for part in [f"HTTP {exc.code}", code, title, detail] if part)


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def write_and_return(
    out_dir: Path,
    checks: list[dict[str, str]],
    errors: list[str],
    env: dict[str, str],
    bundle: dict[str, Any] | None,
    app: dict[str, Any] | None,
) -> dict[str, Any]:
    report = {
        "valid": not errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "errors": errors,
        "summary": {
            "bundle_id": env.get("ASC_BUNDLE_ID", ""),
            "bundle_found": bool(bundle),
            "bundle_resource_id": bundle.get("id", "") if bundle else "",
            "app_found": bool(app),
            "app_id": app.get("id", "") if app else "",
            "app_name": app.get("attributes", {}).get("name", "") if app else "",
            "app_sku": app.get("attributes", {}).get("sku", "") if app else "",
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app_store_record_creation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "app_store_record_creation.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# App Store Record Creation",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- bundle_id: `{summary.get('bundle_id', '')}`",
        f"- bundle_found: `{str(summary.get('bundle_found', False)).lower()}`",
        f"- bundle_resource_id: `{summary.get('bundle_resource_id', '')}`",
        f"- app_found: `{str(summary.get('app_found', False)).lower()}`",
        f"- app_id: `{summary.get('app_id', '')}`",
        f"- app_name: `{summary.get('app_name', '')}`",
        f"- app_sku: `{summary.get('app_sku', '')}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
