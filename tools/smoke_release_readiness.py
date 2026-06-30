from __future__ import annotations

import argparse
from base64 import b64decode
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator

from fastapi.testclient import TestClient

from gitai_phase0.budget_smoke import run_appraisal_budget_smoke, write_appraisal_budget_smoke_report
from gitai_phase0.api import build_state_from_env, create_app

try:
    from tools.smoke_first_play_api import smoke_first_play_api
    from tools.rollback_release_candidate import rollback_release_candidate
    from tools.validate_phase4_seed_ghosts import build_report as build_seed_ghost_report
    from tools.validate_release_candidate import release_linkage_errors, validate_release_candidate
except ModuleNotFoundError:
    from smoke_first_play_api import smoke_first_play_api
    from rollback_release_candidate import rollback_release_candidate
    from validate_phase4_seed_ghosts import build_report as build_seed_ghost_report
    from validate_release_candidate import release_linkage_errors, validate_release_candidate


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "release_readiness"
DEFAULT_PROMOTION_REPORT = ROOT / "reports" / "phase2" / "seed_score_promotion_smoke" / "promotion_report.json"
DEFAULT_DAILY_PLAN_REPORT = ROOT / "reports" / "phase2" / "daily_puzzle_plan_smoke_repeat" / "daily_puzzle_plan.json"
DEFAULT_APPLY_REPORT = ROOT / "reports" / "release_candidate_apply_smoke" / "apply_release_candidate.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a read-only release readiness smoke check for gitai.")
    parser.add_argument("--promotion-report", type=Path, default=DEFAULT_PROMOTION_REPORT)
    parser.add_argument("--daily-plan-report", type=Path, default=DEFAULT_DAILY_PLAN_REPORT)
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--seed-scores", type=Path, default=ROOT / "data" / "scoring" / "seed_scores.json")
    parser.add_argument("--daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--object-catalog", type=Path, default=ROOT / "data" / "puzzle" / "object_catalog.json")
    parser.add_argument("--seed-ghosts", type=Path, default=ROOT / "data" / "competition" / "seed_ghosts.json")
    parser.add_argument("--apply-report", type=Path, default=DEFAULT_APPLY_REPORT)
    parser.add_argument("--web-dist", type=Path, default=ROOT / "web" / "dist")
    parser.add_argument("--static-smoke", type=Path, default=ROOT / "reports" / "phase3_static_smoke.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--season-id", default="season-1")
    parser.add_argument("--today", default="")
    parser.add_argument("--budget-smoke-requests", type=int, default=25)
    parser.add_argument("--budget-smoke-daily-cap", type=int, default=5)
    parser.add_argument("--skip-rollback", action="store_true")
    args = parser.parse_args()

    report = smoke_release_readiness(
        promotion_report_path=args.promotion_report,
        daily_plan_report_path=args.daily_plan_report,
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        daily_puzzles_path=args.daily_puzzles,
        object_catalog_path=args.object_catalog,
        seed_ghosts_path=args.seed_ghosts,
        apply_report_path=args.apply_report,
        web_dist_dir=args.web_dist,
        static_smoke_path=args.static_smoke,
        out_dir=args.out_dir,
        season_id=args.season_id,
        today=args.today or None,
        budget_smoke_requests=args.budget_smoke_requests,
        budget_smoke_daily_cap=args.budget_smoke_daily_cap,
        require_rollback=not args.skip_rollback,
    )
    print(f"Wrote {args.out_dir / 'release_readiness.json'}")
    print(f"Wrote {args.out_dir / 'release_readiness.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def smoke_release_readiness(
    promotion_report_path: Path,
    daily_plan_report_path: Path,
    pairs_path: Path,
    seed_scores_path: Path,
    daily_puzzles_path: Path,
    seed_ghosts_path: Path,
    apply_report_path: Path,
    web_dist_dir: Path,
    static_smoke_path: Path,
    out_dir: Path,
    season_id: str = "season-1",
    today: str | None = None,
    require_rollback: bool = True,
    object_catalog_path: Path | None = None,
    budget_smoke_requests: int = 25,
    budget_smoke_daily_cap: int = 5,
) -> dict[str, Any]:
    object_catalog_path = object_catalog_path or ROOT / "data" / "puzzle" / "object_catalog.json"
    report: dict[str, Any] = {
        "valid": False,
        "season_id": season_id,
        "summary": {},
        "checks": [],
        "errors": [],
        "warnings": [],
        "paths": {
            "pairs": str(pairs_path),
            "seed_scores": str(seed_scores_path),
            "daily_puzzles": str(daily_puzzles_path),
            "object_catalog": str(object_catalog_path),
            "seed_ghosts": str(seed_ghosts_path),
            "promotion_report": str(promotion_report_path),
            "daily_plan_report": str(daily_plan_report_path),
            "apply_report": str(apply_report_path),
            "web_dist": str(web_dist_dir),
            "static_smoke": str(static_smoke_path),
        },
        "release_candidate_validation": {},
        "seed_ghost_report": {},
        "rollback_dry_run": {},
        "api_smoke": {},
        "first_play_api": {},
        "phase5_budget_smoke": {},
        "web_static": {},
    }
    checks: list[dict[str, Any]] = report["checks"]
    errors: list[str] = report["errors"]
    warnings: list[str] = report["warnings"]

    required_paths = {
        "pairs": pairs_path,
        "seed_scores": seed_scores_path,
        "daily_puzzles": daily_puzzles_path,
        "object_catalog": object_catalog_path,
        "seed_ghosts": seed_ghosts_path,
    }
    missing = [f"{name}: {path}" for name, path in required_paths.items() if not path.exists()]
    add_check(
        checks,
        errors,
        "canonical_files_exist",
        not missing,
        "; ".join(missing) if missing else "all canonical files exist",
    )
    if missing:
        return write_report(out_dir, finalize_report(report))

    pairs_payload = load_json(pairs_path)
    seed_scores_payload = load_json(seed_scores_path)
    daily_payload = load_json(daily_puzzles_path)
    seed_ghost_payload = load_json(seed_ghosts_path)

    pair_by_id = {str(item.get("pair_id")): item for item in pairs_payload.get("pairs", [])}
    ref_by_version = {
        str(item.get("ref_version")): item for item in seed_scores_payload.get("seed_scores", [])
    }
    daily_entries = list(daily_payload.get("daily_puzzles", []))
    latest = today or latest_daily_date(daily_entries)

    add_check(checks, errors, "pairs_are_available", bool(pair_by_id), f"{len(pair_by_id)} pairs")
    add_check(
        checks,
        errors,
        "seed_scores_are_available",
        bool(ref_by_version),
        f"{len(ref_by_version)} seed score refs",
    )
    add_check(checks, errors, "daily_puzzles_are_available", bool(daily_entries), f"{len(daily_entries)} daily puzzles")
    add_check(
        checks,
        errors,
        "seed_ghosts_are_available",
        bool(seed_ghost_payload.get("seed_ghosts")),
        f"{len(seed_ghost_payload.get('seed_ghosts', []))} seed ghosts",
    )

    daily_dates = [str(item.get("date")) for item in daily_entries]
    add_check(
        checks,
        errors,
        "daily_dates_are_unique",
        len(daily_dates) == len(set(daily_dates)),
        "DailyPuzzle dates are unique",
    )
    linkage_errors = release_linkage_errors(daily_entries, pair_by_id, ref_by_version)
    add_check(
        checks,
        errors,
        "daily_entries_reference_known_pairs_and_refs",
        not linkage_errors,
        "; ".join(linkage_errors) if linkage_errors else "all DailyPuzzle entries resolve",
    )

    seed_ghost_report = build_seed_ghost_report(
        daily_puzzles_path=daily_puzzles_path,
        pairs_path=pairs_path,
        seed_ghosts_path=seed_ghosts_path,
        season_id=season_id,
    )
    report["seed_ghost_report"] = {
        "valid": seed_ghost_report.valid,
        "daily_count": seed_ghost_report.daily_count,
        "seed_count": seed_ghost_report.seed_count,
        "errors": list(seed_ghost_report.errors),
    }
    add_check(
        checks,
        errors,
        "seed_ghosts_cover_daily_entries",
        seed_ghost_report.valid,
        "; ".join(seed_ghost_report.errors) if seed_ghost_report.errors else "seed ghosts cover every day",
    )

    if promotion_report_path.exists() and daily_plan_report_path.exists():
        candidate = validate_release_candidate(
            promotion_report_path=promotion_report_path,
            daily_plan_report_path=daily_plan_report_path,
            pairs_path=pairs_path,
            seed_scores_path=seed_scores_path,
            daily_puzzles_path=daily_puzzles_path,
            seed_ghosts_path=seed_ghosts_path,
            out_dir=out_dir / "release_candidate_validation",
            season_id=season_id,
            min_planned=0,
        )
        report["release_candidate_validation"] = {
            "valid": candidate["valid"],
            "summary": candidate["summary"],
            "errors": candidate["errors"],
            "warnings": candidate["warnings"],
            "report": str(out_dir / "release_candidate_validation" / "release_candidate.json"),
        }
        add_check(
            checks,
            errors,
            "release_candidate_validation_passes",
            bool(candidate["valid"]),
            "canonical bundle validates against release candidate checks",
        )
    else:
        warnings.append("release candidate source reports are missing; skipped release candidate rebuild check")

    if require_rollback:
        if apply_report_path.exists():
            rollback = rollback_release_candidate(
                apply_report_path=apply_report_path,
                out_dir=out_dir / "rollback_dry_run",
                apply=False,
            )
            report["rollback_dry_run"] = {
                "valid": rollback["valid"],
                "rolled_back": rollback["rolled_back"],
                "file_count": len(rollback.get("files", [])),
                "seed_ghost_image_count": len(rollback.get("seed_ghost_images", [])),
                "errors": rollback["errors"],
                "warnings": rollback["warnings"],
                "report": str(out_dir / "rollback_dry_run" / "rollback_release_candidate.json"),
            }
            add_check(
                checks,
                errors,
                "rollback_dry_run_ready",
                bool(rollback["valid"]) and not rollback["rolled_back"],
                "rollback dry-run is valid and did not mutate canonical data",
            )
        else:
            add_check(checks, errors, "rollback_dry_run_ready", False, f"apply report missing: {apply_report_path}")
    else:
        warnings.append("rollback dry-run was skipped by request")

    web_static = check_web_static(web_dist_dir=web_dist_dir, static_smoke_path=static_smoke_path)
    report["web_static"] = web_static
    add_check(checks, errors, "web_dist_assets_exist", web_static["assets_ok"], web_static["asset_detail"])
    add_check(
        checks,
        errors,
        "phase3_static_smoke_passes",
        web_static["static_smoke_ok"],
        web_static["static_smoke_detail"],
    )

    if latest:
        api_smoke = run_api_smoke(
            pairs_path=pairs_path,
            seed_scores_path=seed_scores_path,
            daily_puzzles_path=daily_puzzles_path,
            seed_ghosts_path=seed_ghosts_path,
            season_id=season_id,
            today=latest,
        )
        report["api_smoke"] = api_smoke
        add_check(
            checks,
            errors,
            "api_smoke_passes_latest_daily",
            api_smoke["valid"],
            "; ".join(api_smoke["errors"]) if api_smoke["errors"] else f"API smoke passed for {latest}",
        )
    else:
        add_check(checks, errors, "api_smoke_passes_latest_daily", False, "no DailyPuzzle date available")

    if latest:
        first_play = smoke_first_play_api(
            pairs_path=pairs_path,
            seed_scores_path=seed_scores_path,
            daily_puzzles_path=daily_puzzles_path,
            object_catalog_path=object_catalog_path,
            seed_ghosts_path=seed_ghosts_path,
            out_dir=out_dir / "first_play_api",
            season_id=season_id,
            today=latest,
        )
        report["first_play_api"] = {
            "valid": first_play["valid"],
            "summary": first_play["summary"],
            "errors": first_play["errors"],
            "report": str(out_dir / "first_play_api" / "first_play_api.json"),
        }
        add_check(
            checks,
            errors,
            "first_play_api_flow_passes",
            bool(first_play["valid"]),
            "; ".join(first_play["errors"]) if first_play["errors"] else "first player flow passed",
        )
    else:
        add_check(checks, errors, "first_play_api_flow_passes", False, "no DailyPuzzle date available")

    budget_smoke = run_phase5_budget_smoke(
        pairs_path=pairs_path,
        out_dir=out_dir / "phase5_budget_smoke",
        request_count=budget_smoke_requests,
        daily_cap_units=budget_smoke_daily_cap,
    )
    report["phase5_budget_smoke"] = budget_smoke
    add_check(
        checks,
        errors,
        "phase5_layer2_budget_gate_passes",
        bool(budget_smoke["gate_passed"]),
        (
            f"daily_spend={budget_smoke['daily_spend']} cap={budget_smoke['daily_cap_units']} "
            f"degraded={str(budget_smoke['degraded_gracefully']).lower()}"
        ),
    )

    latest_entry = next((item for item in daily_entries if str(item.get("date")) == latest), {})
    report["summary"] = {
        "pair_count": len(pair_by_id),
        "seed_score_count": len(ref_by_version),
        "daily_count": len(daily_entries),
        "seed_ghost_count": len(seed_ghost_payload.get("seed_ghosts", [])),
        "latest_date": latest,
        "latest_pair_id": str(latest_entry.get("pair_id", "")),
        "latest_ref_version": str(latest_entry.get("ref_version", "")),
        "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
        "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
    }
    return write_report(out_dir, finalize_report(report))


def run_api_smoke(
    pairs_path: Path,
    seed_scores_path: Path,
    daily_puzzles_path: Path,
    seed_ghosts_path: Path,
    season_id: str,
    today: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "valid": False,
        "today": today,
        "checks": [],
        "errors": [],
        "daily_puzzle": {},
        "daily_puzzles_count": 0,
        "leaderboard_top": {},
        "ghosts": {},
        "archived_daily_puzzles": [],
        "score_deterministic": False,
    }
    checks: list[dict[str, Any]] = result["checks"]
    errors: list[str] = result["errors"]

    with tempfile.TemporaryDirectory(prefix="gitai-release-readiness-") as tmpdir:
        tmp = Path(tmpdir)
        env = {
            "GITAI_PAIRS_PATH": str(pairs_path),
            "GITAI_SEED_SCORES_PATH": str(seed_scores_path),
            "GITAI_DAILY_PUZZLES_PATH": str(daily_puzzles_path),
            "GITAI_SEED_GHOSTS": str(seed_ghosts_path),
            "GITAI_RUNTIME_DB": str(tmp / "runtime.sqlite"),
            "GITAI_IMAGE_STORE": str(tmp / "submissions"),
            "GITAI_MODEL": "heuristic",
            "GITAI_OCR": "fingerprint",
            "GITAI_MODERATION": "fingerprint",
            "GITAI_TODAY": today,
            "GITAI_SEASON_ID": season_id,
            "GITAI_LAYER2_ACTOR": "null",
            "GITAI_DAILY_SUBMISSION_LIMIT": "100",
        }
        with patched_env(env, remove=("GITAI_DAILY_REF_VERSION", "GITAI_SEASON_MODEL_VERSION")):
            client = TestClient(create_app(build_state_from_env()))

            health = client.get("/healthz")
            add_check(checks, errors, "healthz", health.status_code == 200, response_detail(health))

            daily = client.get("/v1/daily-puzzle")
            add_check(checks, errors, "daily_puzzle_current", daily.status_code == 200, response_detail(daily))
            daily_body = daily.json() if daily.status_code == 200 else {}
            result["daily_puzzle"] = {
                "date": str(daily_body.get("date", "")),
                "pair_id": str(daily_body.get("pair_id", "")),
                "ref_version": str(daily_body.get("ref_version", "")),
            }

            archive = client.get("/v1/daily-puzzles")
            archive_ok = archive.status_code == 200 and bool(archive.json().get("entries", []))
            add_check(checks, errors, "daily_puzzles_archive", archive_ok, response_detail(archive))
            if archive.status_code == 200:
                archive_entries = archive.json().get("entries", [])
                result["daily_puzzles_count"] = len(archive_entries)
                archived_daily_errors: list[str] = []
                for entry in archive_entries:
                    entry_date = str(entry.get("date", ""))
                    dated = client.get(f"/v1/daily-puzzle?date={entry_date}")
                    result["archived_daily_puzzles"].append(
                        {
                            "date": entry_date,
                            "status_code": dated.status_code,
                            "pair_id": dated.json().get("pair_id", "") if dated.status_code == 200 else "",
                            "ref_version": dated.json().get("ref_version", "") if dated.status_code == 200 else "",
                        }
                    )
                    if dated.status_code != 200:
                        archived_daily_errors.append(f"{entry_date}: {response_detail(dated)}")
                add_check(
                    checks,
                    errors,
                    "archived_daily_puzzles_load",
                    not archived_daily_errors,
                    "; ".join(archived_daily_errors)
                    if archived_daily_errors
                    else f"{len(archive_entries)} archived DailyPuzzle entries load",
                )

            leaderboard = client.get(f"/v1/leaderboard?date={today}&kind=score")
            leaderboard_body = leaderboard.json() if leaderboard.status_code == 200 else {}
            leaderboard_entries = leaderboard_body.get("entries", [])
            add_check(
                checks,
                errors,
                "score_leaderboard_seeded",
                leaderboard.status_code == 200 and bool(leaderboard_entries),
                response_detail(leaderboard),
            )
            if leaderboard_entries:
                result["leaderboard_top"] = {
                    "submission_id": leaderboard_entries[0].get("submission_id", ""),
                    "score": leaderboard_entries[0].get("score", 0),
                    "bucket": leaderboard_entries[0].get("bucket", ""),
                }

            score_ghost = client.get(f"/v1/ghost?date={today}&kind=score")
            efficiency_ghost = client.get(f"/v1/ghost?date={today}&kind=efficiency")
            score_ghost_ok = (
                score_ghost.status_code == 200
                and image_b64_is_png(score_ghost.json().get("image_b64", ""))
            )
            efficiency_ghost_ok = (
                efficiency_ghost.status_code == 200
                and image_b64_is_png(efficiency_ghost.json().get("image_b64", ""))
            )
            add_check(checks, errors, "score_ghost_available", score_ghost_ok, response_detail(score_ghost))
            add_check(
                checks,
                errors,
                "efficiency_ghost_available",
                efficiency_ghost_ok,
                response_detail(efficiency_ghost),
            )
            result["ghosts"] = {
                "score": ghost_summary(score_ghost),
                "efficiency": ghost_summary(efficiency_ghost),
            }

            if daily.status_code == 200 and score_ghost.status_code == 200:
                payload = {
                    "image_b64": score_ghost.json()["image_b64"],
                    "pair_id": daily_body["pair_id"],
                    "ref_version": daily_body["ref_version"],
                }
                first = client.post("/v1/score", json=payload)
                second = client.post("/v1/score", json=payload)
                deterministic = (
                    first.status_code == 200
                    and second.status_code == 200
                    and stable_score_payload(first.json()) == stable_score_payload(second.json())
                )
                add_check(checks, errors, "score_endpoint_deterministic", deterministic, response_detail(first))
                result["score_deterministic"] = deterministic

    result["valid"] = not errors
    return result


def run_phase5_budget_smoke(
    pairs_path: Path,
    out_dir: Path,
    request_count: int,
    daily_cap_units: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gitai-release-budget-") as tmpdir:
        report = run_appraisal_budget_smoke(
            runtime_db=Path(tmpdir) / "budget-smoke.sqlite",
            pairs_path=pairs_path,
            request_count=request_count,
            daily_cap_units=daily_cap_units,
        )
    json_path, markdown_path = write_appraisal_budget_smoke_report(report, out_dir)
    payload = report.to_dict()
    payload["report"] = str(json_path)
    payload["markdown"] = str(markdown_path)
    return payload


def check_web_static(web_dist_dir: Path, static_smoke_path: Path) -> dict[str, Any]:
    index = web_dist_dir / "index.html"
    if not index.exists():
        return {
            "assets_ok": False,
            "asset_detail": f"missing {index}",
            "static_smoke_ok": False,
            "static_smoke_detail": "static smoke cannot run without web dist",
        }
    html = index.read_text(encoding="utf-8")
    scripts = re.findall(r'src="([^"]+\.js)"', html)
    styles = re.findall(r'href="([^"]+\.css)"', html)
    missing_assets = [
        str(web_dist_dir / path.lstrip("/"))
        for path in [*scripts, *styles]
        if not (web_dist_dir / path.lstrip("/")).exists()
    ]
    assets_ok = bool(scripts) and bool(styles) and not missing_assets

    if not static_smoke_path.exists():
        return {
            "assets_ok": assets_ok,
            "asset_detail": "web dist assets resolve" if assets_ok else f"missing assets: {missing_assets}",
            "static_smoke_ok": False,
            "static_smoke_detail": f"missing {static_smoke_path}",
        }
    static_payload = load_json(static_smoke_path)
    static_checks = static_payload.get("checks", {})
    failed_static = [name for name, passed in static_checks.items() if not passed]
    return {
        "assets_ok": assets_ok,
        "asset_detail": "web dist assets resolve" if assets_ok else f"missing assets: {missing_assets}",
        "static_smoke_ok": bool(static_checks) and not failed_static,
        "static_smoke_detail": (
            "all static checks pass"
            if static_checks and not failed_static
            else f"failed static checks: {failed_static}"
        ),
        "scripts": scripts,
        "styles": styles,
        "static_check_count": len(static_checks),
    }


def add_check(
    checks: list[dict[str, Any]],
    errors: list[str],
    name: str,
    passed: bool,
    detail: str,
) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})
    if not passed:
        errors.append(f"{name}: {detail}")


def latest_daily_date(daily_entries: list[dict[str, Any]]) -> str:
    parsed: list[date] = []
    for item in daily_entries:
        try:
            parsed.append(date.fromisoformat(str(item["date"])))
        except (KeyError, ValueError):
            continue
    return max(parsed).isoformat() if parsed else ""


def stable_score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(payload)
    copied.pop("computed_at", None)
    return copied


def image_b64_is_png(value: str) -> bool:
    if not value:
        return False
    try:
        return b64decode(value).startswith(b"\x89PNG\r\n\x1a\n")
    except Exception:
        return False


def ghost_summary(response) -> dict[str, Any]:
    if response.status_code != 200:
        return {"status_code": response.status_code}
    body = response.json()
    return {
        "status_code": response.status_code,
        "submission_id": body.get("submission_id", ""),
        "score": body.get("score", 0),
        "bucket": body.get("bucket", ""),
        "image_png": image_b64_is_png(body.get("image_b64", "")),
    }


def response_detail(response) -> str:
    if response.status_code < 400:
        return f"status {response.status_code}"
    try:
        return f"status {response.status_code}: {response.json().get('detail', response.text)}"
    except Exception:
        return f"status {response.status_code}: {response.text}"


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


def finalize_report(report: dict[str, Any]) -> dict[str, Any]:
    report["valid"] = not report["errors"]
    if not report.get("summary"):
        report["summary"] = {
            "passed_checks": sum(1 for item in report["checks"] if item["status"] == "pass"),
            "failed_checks": sum(1 for item in report["checks"] if item["status"] == "fail"),
        }
    return report


def write_report(out_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "release_readiness.json", report)
    (out_dir / "release_readiness.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Release readiness smoke",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- season_id: `{report['season_id']}`",
        f"- latest_date: `{summary.get('latest_date', '')}`",
        f"- latest_pair_id: `{summary.get('latest_pair_id', '')}`",
        f"- daily_count: `{summary.get('daily_count', 0)}`",
        f"- seed_ghost_count: `{summary.get('seed_ghost_count', 0)}`",
        f"- passed_checks: `{summary.get('passed_checks', 0)}`",
        f"- failed_checks: `{summary.get('failed_checks', 0)}`",
        "",
        "## Checks",
        "",
        "| check | status | detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item['name']} | {item['status']} | {item['detail']} |" for item in report["checks"])
    api = report.get("api_smoke", {})
    if api:
        lines.extend(
            [
                "",
                "## API Smoke",
                "",
                f"- today: `{api.get('today', '')}`",
                f"- daily_puzzle: `{api.get('daily_puzzle', {}).get('pair_id', '')}`",
                f"- score_deterministic: `{str(api.get('score_deterministic', False)).lower()}`",
            ]
        )
    first_play = report.get("first_play_api", {})
    if first_play:
        first_summary = first_play.get("summary", {})
        lines.extend(
            [
                "",
                "## First Play",
                "",
                f"- valid: `{str(first_play.get('valid', False)).lower()}`",
                f"- submission_id: `{first_summary.get('submission_id', '')}`",
                f"- score: `{first_summary.get('score', 0)}`",
            ]
        )
    budget = report.get("phase5_budget_smoke", {})
    if budget:
        lines.extend(
            [
                "",
                "## Phase 5 Budget",
                "",
                f"- gate_passed: `{str(budget.get('gate_passed', False)).lower()}`",
                f"- daily_spend: `{budget.get('daily_spend', 0)}` / `{budget.get('daily_cap_units', 0)}`",
                f"- degraded_gracefully: `{str(budget.get('degraded_gracefully', False)).lower()}`",
            ]
        )
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
