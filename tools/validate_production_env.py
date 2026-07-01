from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "production_env_validation"

REQUIRED_KEYS = (
    "GITAI_CORS_ORIGINS",
    "GITAI_PUBLIC_WEB_URL",
    "GITAI_STATIC_DIR",
    "GITAI_RUNTIME_DB",
    "GITAI_IMAGE_STORE",
    "GITAI_MODEL",
    "GITAI_OCR",
    "GITAI_MODERATION",
    "GITAI_SEASON_ID",
    "GITAI_SEASON_LABEL",
    "GITAI_DAILY_LLM_SPEND_CAP",
    "GITAI_USER_DAILY_COMMENT_LIMIT",
    "GITAI_DAILY_SUBMISSION_LIMIT",
    "GITAI_OPERATOR_TOKEN",
)
PLACEHOLDER_TOKENS = ("example", "replace-with", "your-public", "localhost", "127.0.0.1")
SAFE_MODELS = {"heuristic", "open_clip", "siglip"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate gitai production-facing environment settings.")
    parser.add_argument("--env-file", type=Path, default=None, help="Optional dotenv-style file to validate.")
    parser.add_argument("--allow-placeholders", action="store_true", help="Accept template placeholder values.")
    parser.add_argument("--check-paths", action="store_true", help="Require local filesystem paths to exist.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    env = dict(os.environ)
    source = "process"
    if args.env_file is not None:
        env.update(parse_env_file(args.env_file))
        source = str(args.env_file)
    report = validate_production_env(
        env,
        source=source,
        allow_placeholders=args.allow_placeholders,
        check_paths=args.check_paths,
    )
    write_report(args.out_dir, report)
    print(f"Wrote {args.out_dir / 'production_env_validation.json'}")
    print(f"Wrote {args.out_dir / 'production_env_validation.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def validate_production_env(
    env: dict[str, str],
    source: str = "process",
    allow_placeholders: bool = False,
    check_paths: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    missing = [key for key in REQUIRED_KEYS if not env.get(key, "").strip()]
    add_check(
        checks,
        errors,
        "required_keys_present",
        not missing,
        "all required keys present" if not missing else f"missing={missing}",
    )

    public_url = env.get("GITAI_PUBLIC_WEB_URL", "").strip()
    add_check(
        checks,
        errors,
        "public_web_url_is_https",
        is_https_url(public_url),
        public_url or "missing",
    )
    add_check(
        checks,
        errors,
        "public_web_url_not_placeholder",
        allow_placeholders or not contains_placeholder(public_url),
        public_url or "missing",
    )

    cors_origins = parse_csv(env.get("GITAI_CORS_ORIGINS", ""))
    cors_ok = bool(cors_origins) and all(is_production_cors_origin(origin) for origin in cors_origins)
    cors_placeholder_ok = allow_placeholders or not any(origin_contains_placeholder(origin) for origin in cors_origins)
    add_check(
        checks,
        errors,
        "cors_origins_are_production_origins",
        cors_ok,
        ", ".join(cors_origins) if cors_origins else "missing",
    )
    add_check(
        checks,
        errors,
        "cors_origins_not_placeholder",
        cors_placeholder_ok,
        ", ".join(cors_origins) if cors_origins else "missing",
    )

    add_check(
        checks,
        errors,
        "model_and_guards_are_production_safe",
        env.get("GITAI_MODEL") in SAFE_MODELS
        and env.get("GITAI_OCR") == "fingerprint"
        and env.get("GITAI_MODERATION") == "fingerprint",
        f"model={env.get('GITAI_MODEL', '')} ocr={env.get('GITAI_OCR', '')} moderation={env.get('GITAI_MODERATION', '')}",
    )

    positive_numbers = {
        "GITAI_DAILY_LLM_SPEND_CAP": env.get("GITAI_DAILY_LLM_SPEND_CAP", ""),
        "GITAI_USER_DAILY_COMMENT_LIMIT": env.get("GITAI_USER_DAILY_COMMENT_LIMIT", ""),
        "GITAI_DAILY_SUBMISSION_LIMIT": env.get("GITAI_DAILY_SUBMISSION_LIMIT", ""),
    }
    bad_numbers = [key for key, value in positive_numbers.items() if not is_positive_int(value)]
    add_check(
        checks,
        errors,
        "limits_are_positive_integers",
        not bad_numbers,
        json.dumps(positive_numbers, sort_keys=True),
    )

    season_id = env.get("GITAI_SEASON_ID", "")
    add_check(
        checks,
        errors,
        "season_identity_is_set",
        bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", season_id))
        and bool(env.get("GITAI_SEASON_LABEL", "").strip()),
        f"season_id={season_id} season_label={env.get('GITAI_SEASON_LABEL', '')}",
    )

    token = env.get("GITAI_OPERATOR_TOKEN", "")
    token_ok = len(token) >= 32 and not weak_secret(token)
    add_check(
        checks,
        errors,
        "operator_token_is_strong",
        allow_placeholders or token_ok,
        "placeholder accepted for template" if allow_placeholders and not token_ok else f"length={len(token)}",
    )
    if allow_placeholders and not token_ok:
        warnings.append("GITAI_OPERATOR_TOKEN is a template placeholder; replace it with a 32+ character random value.")

    if check_paths:
        paths = {
            "GITAI_STATIC_DIR": env.get("GITAI_STATIC_DIR", ""),
            "GITAI_RUNTIME_DB_PARENT": str(Path(env.get("GITAI_RUNTIME_DB", "")).parent),
            "GITAI_IMAGE_STORE": env.get("GITAI_IMAGE_STORE", ""),
        }
        missing_paths = [key for key, value in paths.items() if not value or not Path(value).exists()]
        add_check(
            checks,
            errors,
            "local_paths_exist",
            not missing_paths,
            json.dumps(paths, sort_keys=True),
        )

    return {
        "valid": not errors,
        "source": source,
        "allow_placeholders": allow_placeholders,
        "check_paths": check_paths,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "warnings": len(warnings),
        },
    }


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.path.rstrip("/")


def is_capacitor_origin(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "capacitor" and parsed.netloc == "localhost" and not parsed.path.rstrip("/")


def is_production_cors_origin(value: str) -> bool:
    return is_https_url(value) or is_capacitor_origin(value)


def contains_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in PLACEHOLDER_TOKENS)


def origin_contains_placeholder(value: str) -> bool:
    if is_capacitor_origin(value):
        return False
    return contains_placeholder(value)


def is_positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False


def weak_secret(value: str) -> bool:
    lowered = value.lower()
    return contains_placeholder(lowered) or len(set(value)) < 8


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "production_env_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "production_env_validation.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Production Env Validation",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- source: `{report['source']}`",
        f"- allow_placeholders: `{str(report['allow_placeholders']).lower()}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        f"- warnings: `{summary['warnings']}`",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
