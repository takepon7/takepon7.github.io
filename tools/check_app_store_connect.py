from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import subprocess
import time
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".env.appstore"
DEFAULT_OUT_DIR = ROOT / "reports" / "app_store_connect"
ASC_API = "https://api.appstoreconnect.apple.com"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check App Store Connect API credentials without printing secrets.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = check_app_store_connect(args.env_file, args.out_dir)
    print(f"Wrote {args.out_dir / 'app_store_connect.json'}")
    print(f"Wrote {args.out_dir / 'app_store_connect.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def check_app_store_connect(env_file: Path, out_dir: Path) -> dict[str, Any]:
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

    private_key = Path(env.get("ASC_PRIVATE_KEY_PATH", ""))
    if private_key and not private_key.is_absolute():
        private_key = (env_file.parent / private_key).resolve()
    key_exists = private_key.exists()
    add_check(checks, errors, "private_key_exists", key_exists, redact_path(private_key))

    token = ""
    if not missing and key_exists:
        try:
            token = build_jwt(
                key_id=env["ASC_KEY_ID"],
                issuer_id=env["ASC_ISSUER_ID"],
                private_key=private_key,
            )
            add_check(checks, errors, "jwt_generated", True, "ES256 token generated")
        except Exception as exc:  # noqa: BLE001
            add_check(checks, errors, "jwt_generated", False, type(exc).__name__)
    else:
        add_check(checks, errors, "jwt_generated", False, "skipped")

    bundle_lookup: dict[str, Any] = {}
    if token:
        try:
            bundle_lookup = api_get(
                token,
                "/v1/bundleIds",
                {"filter[identifier]": env["ASC_BUNDLE_ID"], "limit": "1"},
            )
            ok = "data" in bundle_lookup
            count = len(bundle_lookup.get("data", [])) if isinstance(bundle_lookup.get("data"), list) else 0
            add_check(checks, errors, "bundle_ids_endpoint_reachable", ok, f"matched_bundle_ids={count}")
        except HTTPError as exc:
            add_check(checks, errors, "bundle_ids_endpoint_reachable", False, f"HTTP {exc.code}")
        except URLError as exc:
            add_check(checks, errors, "bundle_ids_endpoint_reachable", False, type(exc.reason).__name__)
    else:
        add_check(checks, errors, "bundle_ids_endpoint_reachable", False, "skipped")

    bundle_data = bundle_lookup.get("data", []) if isinstance(bundle_lookup.get("data"), list) else []
    matched_bundle = bundle_data[0] if bundle_data else None
    if matched_bundle:
        attrs = matched_bundle.get("attributes", {})
        add_check(
            checks,
            errors,
            "bundle_id_found",
            True,
            json.dumps(
                {
                    "id": matched_bundle.get("id", ""),
                    "identifier": attrs.get("identifier", ""),
                    "name": attrs.get("name", ""),
                    "platform": attrs.get("platform", ""),
                },
                sort_keys=True,
                ensure_ascii=False,
            ),
        )
    else:
        add_check(checks, errors, "bundle_id_found", False, f"No bundle ID found for {env.get('ASC_BUNDLE_ID', '')}")

    app_lookup: dict[str, Any] = {}
    if token:
        try:
            app_lookup = api_get(
                token,
                "/v1/apps",
                {"filter[bundleId]": env["ASC_BUNDLE_ID"], "limit": "1"},
            )
            ok = "data" in app_lookup
            count = len(app_lookup.get("data", [])) if isinstance(app_lookup.get("data"), list) else 0
            add_check(checks, errors, "apps_endpoint_reachable", ok, f"matched_apps={count}")
        except HTTPError as exc:
            detail = f"HTTP {exc.code}"
            add_check(checks, errors, "apps_endpoint_reachable", False, detail)
        except URLError as exc:
            add_check(checks, errors, "apps_endpoint_reachable", False, type(exc.reason).__name__)
    else:
        add_check(checks, errors, "apps_endpoint_reachable", False, "skipped")

    app_data = app_lookup.get("data", []) if isinstance(app_lookup.get("data"), list) else []
    matched_app = app_data[0] if app_data else None
    if matched_app:
        attrs = matched_app.get("attributes", {})
        detail = json.dumps(
            {
                "id": matched_app.get("id", ""),
                "name": attrs.get("name", ""),
                "bundleId": attrs.get("bundleId", env.get("ASC_BUNDLE_ID", "")),
                "sku": attrs.get("sku", ""),
                "primaryLocale": attrs.get("primaryLocale", ""),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        add_check(checks, errors, "app_record_found", True, detail)
    else:
        add_check(
            checks,
            errors,
            "app_record_found",
            False,
            f"No App Store app record found for bundle_id={env.get('ASC_BUNDLE_ID', '')}",
        )

    report = {
        "valid": not errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "errors": errors,
        "summary": {
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "bundle_id": env.get("ASC_BUNDLE_ID", ""),
            "bundle_found": bool(matched_bundle),
            "bundle_resource_id": matched_bundle.get("id", "") if matched_bundle else "",
            "app_found": bool(matched_app),
            "app_id": matched_app.get("id", "") if matched_app else "",
        },
    }
    write_report(out_dir, report)
    return report


def build_jwt(key_id: str, issuer_id: str, private_key: Path) -> str:
    now = int(time.time())
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + 20 * 60,
        "aud": "appstoreconnect-v1",
    }
    signing_input = f"{b64json(header)}.{b64json(payload)}"
    der = subprocess.check_output(
        ["openssl", "dgst", "-sha256", "-sign", str(private_key)],
        input=signing_input.encode("ascii"),
    )
    signature = der_ecdsa_to_raw(der)
    return f"{signing_input}.{b64url(signature)}"


def api_get(token: str, path: str, params: dict[str, str]) -> dict[str, Any]:
    query = urlencode(params)
    url = f"{ASC_API}{path}?{query}" if query else f"{ASC_API}{path}"
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    context = ssl.create_default_context(cafile=certifi_where())
    with urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def certifi_where() -> str | None:
    try:
        import certifi

        return certifi.where()
    except Exception:  # noqa: BLE001
        return None


def der_ecdsa_to_raw(der: bytes) -> bytes:
    offset = 0
    if der[offset] != 0x30:
        raise ValueError("ECDSA signature is not a DER sequence")
    offset += 1
    _, offset = read_der_length(der, offset)
    r, offset = read_der_integer(der, offset)
    s, offset = read_der_integer(der, offset)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def read_der_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    size = first & 0x7F
    length = int.from_bytes(data[offset : offset + size], "big")
    return length, offset + size


def read_der_integer(data: bytes, offset: int) -> tuple[int, int]:
    if data[offset] != 0x02:
        raise ValueError("Expected DER integer")
    offset += 1
    length, offset = read_der_length(data, offset)
    value = int.from_bytes(data[offset : offset + length], "big")
    return value, offset + length


def b64json(payload: dict[str, Any]) -> str:
    return b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def b64url(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def redact_path(path: Path) -> str:
    parts = path.parts
    if ".secrets" in parts:
        index = parts.index(".secrets")
        return str(Path(*parts[: index + 1]) / "..." / path.name)
    return str(path)


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app_store_connect.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "app_store_connect.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# App Store Connect Check",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- bundle_id: `{summary.get('bundle_id', '')}`",
        f"- bundle_found: `{str(summary.get('bundle_found', False)).lower()}`",
        f"- bundle_resource_id: `{summary.get('bundle_resource_id', '')}`",
        f"- app_found: `{str(summary.get('app_found', False)).lower()}`",
        f"- app_id: `{summary.get('app_id', '')}`",
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
