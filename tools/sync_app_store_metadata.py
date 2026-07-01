from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_app_store_connect import build_jwt, parse_env_file  # noqa: E402
from tools.create_app_store_records import api_request, api_error_detail  # noqa: E402

DEFAULT_ENV = ROOT / ".env.appstore"
DEFAULT_OUT_DIR = ROOT / "reports" / "app_store_connect"

PROMOTIONAL_TEXT = "毎日変わるお題で、AI鑑定士をだませ。描いて、採点されて、ゴーストに挑戦する短時間ドローイングゲーム。"
DESCRIPTION = """gitai は、与えられた素体を別のモノに見えるよう描き足して、AI鑑定士をどこまでだませるか競うドローイングゲームです。

りんごを野球ボールに、トマトを野球ボールに、マグカップを本に。毎日の小さなお題に挑戦して、スコアとランキングを更新しましょう。

特徴:
・毎日更新の擬態お題
・描いた絵をAI鑑定士が即時採点
・ランキングとゴーストリプレイ
・フレンド合言葉で身内ランキング
・結果をシェアできるカード
・アカウント登録なしですぐプレイ

うまく描くゲームではありません。うまく「それっぽく化けさせる」ゲームです。"""
KEYWORDS = "ドローイング,パズル,AI,お絵描き,ランキング,毎日,カジュアル,擬態"
WHATS_NEW = "初回リリース。毎日更新のお題、AI鑑定、ランキング、ゴーストリプレイに対応しました。"
SUBTITLE = "AIをだます擬態ドローイング"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync safe App Store text metadata through App Store Connect API.")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--apply-urls", action="store_true", help="Also sync URL fields if they are non-placeholder HTTPS URLs.")
    args = parser.parse_args()
    report = sync_app_store_metadata(args.env_file, args.out_dir, args.apply_urls)
    print(f"Wrote {args.out_dir / 'app_store_metadata_sync.json'}")
    print(f"Wrote {args.out_dir / 'app_store_metadata_sync.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def sync_app_store_metadata(env_file: Path, out_dir: Path, apply_urls: bool) -> dict[str, Any]:
    env = parse_env_file(env_file)
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    actions: list[dict[str, str]] = []

    private_key = Path(env.get("ASC_PRIVATE_KEY_PATH", ""))
    if not private_key.is_absolute():
        private_key = (env_file.parent / private_key).resolve()
    token = build_jwt(env["ASC_KEY_ID"], env["ASC_ISSUER_ID"], private_key)

    app = find_app(token, env["ASC_BUNDLE_ID"])
    if not app:
        add_check(checks, errors, "app_record_found", False, f"No app record for {env['ASC_BUNDLE_ID']}")
        return write_report(out_dir, checks, errors, actions, {})
    add_check(checks, errors, "app_record_found", True, f"id={app['id']}")

    app_info = first(api_request(token, "GET", f"/v1/apps/{app['id']}/appInfos", params={"limit": "1"}))
    app_version = first(api_request(token, "GET", f"/v1/apps/{app['id']}/appStoreVersions", params={"limit": "1"}))
    if not app_info:
        add_check(checks, errors, "app_info_found", False, "missing app info")
        return write_report(out_dir, checks, errors, actions, {"app_id": app["id"]})
    if not app_version:
        add_check(checks, errors, "app_store_version_found", False, "missing app store version")
        return write_report(out_dir, checks, errors, actions, {"app_id": app["id"]})
    add_check(checks, errors, "app_info_found", True, f"id={app_info['id']}")
    add_check(checks, errors, "app_store_version_found", True, f"id={app_version['id']}")

    info_loc = first(api_request(token, "GET", f"/v1/appInfos/{app_info['id']}/appInfoLocalizations", params={"limit": "10"}))
    version_loc = first(
        api_request(
            token,
            "GET",
            f"/v1/appStoreVersions/{app_version['id']}/appStoreVersionLocalizations",
            params={"limit": "10"},
        )
    )
    if not info_loc or not version_loc:
        add_check(checks, errors, "localizations_found", False, "missing ja localizations")
        return write_report(out_dir, checks, errors, actions, {"app_id": app["id"]})
    add_check(checks, errors, "localizations_found", True, f"info={info_loc['id']} version={version_loc['id']}")

    info_attrs = {"name": env.get("ASC_APP_NAME", "gitai"), "subtitle": SUBTITLE}
    url_actions = []
    if apply_urls and good_url(env.get("GITAI_IOS_PRIVACY_URL", "")):
        info_attrs["privacyPolicyUrl"] = env["GITAI_IOS_PRIVACY_URL"]
        url_actions.append("privacyPolicyUrl")
    patch_with_fallback(
        token,
        f"/v1/appInfoLocalizations/{info_loc['id']}",
        "appInfoLocalizations",
        info_loc["id"],
        info_attrs,
        "appInfoLocalization",
        actions,
    )

    version_attrs = {
        "description": DESCRIPTION,
        "keywords": KEYWORDS,
        "promotionalText": PROMOTIONAL_TEXT,
        "whatsNew": WHATS_NEW,
    }
    if apply_urls and good_url(env.get("GITAI_IOS_MARKETING_URL", "")):
        version_attrs["marketingUrl"] = env["GITAI_IOS_MARKETING_URL"]
        url_actions.append("marketingUrl")
    if apply_urls and good_url(env.get("GITAI_IOS_SUPPORT_URL", "")):
        version_attrs["supportUrl"] = env["GITAI_IOS_SUPPORT_URL"]
        url_actions.append("supportUrl")
    patch_with_fallback(
        token,
        f"/v1/appStoreVersionLocalizations/{version_loc['id']}",
        "appStoreVersionLocalizations",
        version_loc["id"],
        version_attrs,
        "appStoreVersionLocalization",
        actions,
    )

    version_patch_attrs = {"copyright": "© 2026 gitai", "releaseType": "AFTER_APPROVAL", "usesIdfa": False}
    try:
        patch(token, f"/v1/appStoreVersions/{app_version['id']}", "appStoreVersions", app_version["id"], version_patch_attrs)
        actions.append({"target": "appStoreVersion", "status": "updated", "detail": ",".join(sorted(version_patch_attrs))})
    except HTTPError as exc:
        actions.append({"target": "appStoreVersion", "status": "skipped", "detail": api_error_detail(exc)})

    if apply_urls:
        add_check(
            checks,
            errors,
            "url_metadata_synced",
            len(url_actions) == 3,
            f"synced={url_actions}",
        )
    else:
        add_check(checks, errors, "url_metadata_synced", True, "skipped until final production URLs are set")

    return write_report(
        out_dir,
        checks,
        errors,
        actions,
        {
            "app_id": app["id"],
            "app_info_id": app_info["id"],
            "app_store_version_id": app_version["id"],
        },
    )


def find_app(token: str, bundle_id: str) -> dict[str, Any] | None:
    return first(api_request(token, "GET", "/v1/apps", params={"filter[bundleId]": bundle_id, "limit": "1"}))


def first(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data", [])
    if isinstance(data, list) and data:
        return data[0]
    return None


def patch(token: str, path: str, type_name: str, resource_id: str, attributes: dict[str, Any]) -> None:
    api_request(
        token,
        "PATCH",
        path,
        body={"data": {"type": type_name, "id": resource_id, "attributes": attributes}},
    )


def patch_with_fallback(
    token: str,
    path: str,
    type_name: str,
    resource_id: str,
    attributes: dict[str, Any],
    target: str,
    actions: list[dict[str, str]],
) -> None:
    try:
        patch(token, path, type_name, resource_id, attributes)
        actions.append({"target": target, "status": "updated", "detail": ",".join(sorted(attributes))})
        return
    except HTTPError as exc:
        actions.append({"target": target, "status": "bulk_failed", "detail": api_error_detail(exc)})

    for key, value in attributes.items():
        try:
            patch(token, path, type_name, resource_id, {key: value})
            actions.append({"target": f"{target}.{key}", "status": "updated", "detail": key})
        except HTTPError as exc:
            actions.append({"target": f"{target}.{key}", "status": "skipped", "detail": api_error_detail(exc)})


def good_url(value: str) -> bool:
    return value.startswith("https://") and "example.com" not in value


def add_check(checks: list[dict[str, str]], errors: list[str], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def write_report(
    out_dir: Path,
    checks: list[dict[str, str]],
    errors: list[str],
    actions: list[dict[str, str]],
    ids: dict[str, str],
) -> dict[str, Any]:
    report = {
        "valid": not errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "actions": actions,
        "errors": errors,
        "summary": {
            **ids,
            "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
            "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
            "actions": len(actions),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "app_store_metadata_sync.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "app_store_metadata_sync.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# App Store Metadata Sync",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- app_id: `{summary.get('app_id', '')}`",
        f"- app_info_id: `{summary.get('app_info_id', '')}`",
        f"- app_store_version_id: `{summary.get('app_store_version_id', '')}`",
        f"- actions: `{summary.get('actions', 0)}`",
        f"- passed_checks: `{summary['passed_checks']}`",
        f"- failed_checks: `{summary['failed_checks']}`",
        "",
        "## Checks",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    if report["actions"]:
        lines.extend(["", "## Actions", "", "| target | status | detail |", "| --- | --- | --- |"])
        lines.extend(f"| {item['target']} | {item['status']} | {item['detail']} |" for item in report["actions"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
