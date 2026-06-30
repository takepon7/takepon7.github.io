from __future__ import annotations

import argparse
from base64 import b64decode, b64encode
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterator

from fastapi.testclient import TestClient

from gitai_phase0.api import build_state_from_env, create_app
from gitai_phase0.drawing_verification import parse_stroke_log, render_replay
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "first_play_api"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first-play API flow against a temporary runtime DB.")
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--seed-scores", type=Path, default=ROOT / "data" / "scoring" / "seed_scores.json")
    parser.add_argument("--daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--object-catalog", type=Path, default=ROOT / "data" / "puzzle" / "object_catalog.json")
    parser.add_argument("--seed-ghosts", type=Path, default=ROOT / "data" / "competition" / "seed_ghosts.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--season-id", default="season-1")
    parser.add_argument("--today", default="")
    args = parser.parse_args()

    report = smoke_first_play_api(
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        daily_puzzles_path=args.daily_puzzles,
        object_catalog_path=args.object_catalog,
        seed_ghosts_path=args.seed_ghosts,
        out_dir=args.out_dir,
        season_id=args.season_id,
        today=args.today or None,
    )
    print(f"Wrote {args.out_dir / 'first_play_api.json'}")
    print(f"Wrote {args.out_dir / 'first_play_api.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def smoke_first_play_api(
    pairs_path: Path,
    seed_scores_path: Path,
    daily_puzzles_path: Path,
    object_catalog_path: Path,
    seed_ghosts_path: Path,
    out_dir: Path,
    season_id: str = "season-1",
    today: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "valid": False,
        "season_id": season_id,
        "today": today or "",
        "checks": [],
        "errors": [],
        "summary": {},
        "submission": {},
        "archived_submissions": [],
        "proposal": {},
        "paths": {
            "pairs": str(pairs_path),
            "seed_scores": str(seed_scores_path),
            "daily_puzzles": str(daily_puzzles_path),
            "object_catalog": str(object_catalog_path),
            "seed_ghosts": str(seed_ghosts_path),
        },
    }
    checks: list[dict[str, Any]] = report["checks"]
    errors: list[str] = report["errors"]

    today_value = today or latest_daily_date(daily_puzzles_path)
    report["today"] = today_value
    with tempfile.TemporaryDirectory(prefix="gitai-first-play-") as tmpdir:
        tmp = Path(tmpdir)
        env = {
            "GITAI_PAIRS_PATH": str(pairs_path),
            "GITAI_SEED_SCORES_PATH": str(seed_scores_path),
            "GITAI_DAILY_PUZZLES_PATH": str(daily_puzzles_path),
            "GITAI_OBJECT_CATALOG_PATH": str(object_catalog_path),
            "GITAI_SEED_GHOSTS": str(seed_ghosts_path),
            "GITAI_RUNTIME_DB": str(tmp / "runtime.sqlite"),
            "GITAI_IMAGE_STORE": str(tmp / "submissions"),
            "GITAI_MODEL": "heuristic",
            "GITAI_OCR": "fingerprint",
            "GITAI_MODERATION": "fingerprint",
            "GITAI_TODAY": today_value,
            "GITAI_SEASON_ID": season_id,
            "GITAI_LAYER2_ACTOR": "null",
            "GITAI_DAILY_SUBMISSION_LIMIT": "10",
            "GITAI_PREMIUM_REDEEM_CODES": "SMOKEPASS:1",
        }
        with patched_env(env, remove=("GITAI_DAILY_REF_VERSION", "GITAI_SEASON_MODEL_VERSION")):
            client = TestClient(create_app(build_state_from_env()))
            run_flow(client, report, checks, errors)

    report["valid"] = not errors
    report["summary"] = {
        "passed_checks": sum(1 for item in checks if item["status"] == "pass"),
        "failed_checks": sum(1 for item in checks if item["status"] == "fail"),
        "today": today_value,
        "submission_id": report["submission"].get("submission_id", ""),
        "score": report["submission"].get("score", 0),
        "percentile": report["submission"].get("percentile", 0.0),
        "archived_submission_count": len(report["archived_submissions"]),
        "pair_id": report["summary"].get("pair_id", ""),
    }
    write_report(out_dir, report)
    return report


def run_flow(
    client: TestClient,
    report: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> None:
    health = client.get("/healthz")
    add_response_check(checks, errors, "healthz", health)
    add_check(
        checks,
        errors,
        "api_security_headers_present",
        has_security_headers(health),
        "public API security headers are present",
    )

    archive = client.get("/v1/daily-puzzles")
    add_response_check(checks, errors, "daily_archive_loads", archive)
    archive_entries = archive.json().get("entries", []) if archive.status_code == 200 else []
    add_check(checks, errors, "daily_archive_has_entries", bool(archive_entries), f"{len(archive_entries)} entries")

    daily = client.get("/v1/daily-puzzle")
    add_response_check(checks, errors, "current_daily_loads", daily)
    if daily.status_code != 200:
        return
    daily_body = daily.json()
    report["summary"].update(
        {
            "date": daily_body["date"],
            "pair_id": daily_body["pair_id"],
            "ref_version": daily_body["ref_version"],
            "base": daily_body["base"]["canonical_label"],
            "target": daily_body["target"]["canonical_label"],
        }
    )

    add_response_check(checks, errors, "premium_status_loads", client.get("/v1/premium?user_id=first-player"))
    cosmetics = client.get(f"/v1/cosmetics?user_id=first-player&season_id={daily_body['season_id']}")
    add_response_check(checks, errors, "cosmetics_load", cosmetics)
    if cosmetics.status_code == 200:
        add_check(
            checks,
            errors,
            "default_cosmetic_available",
            bool(cosmetics.json().get("cosmetics", [])),
            "default palette is listed",
        )

    score_ghost = client.get(f"/v1/ghost?date={daily_body['date']}&kind=score")
    efficiency_ghost = client.get(f"/v1/ghost?date={daily_body['date']}&kind=efficiency")
    add_response_check(checks, errors, "score_ghost_loads", score_ghost)
    add_response_check(checks, errors, "efficiency_ghost_loads", efficiency_ghost)
    if score_ghost.status_code == 200:
        score_ghost_log = score_ghost.json().get("stroke_log")
        add_check(
            checks,
            errors,
            "score_ghost_has_png",
            is_png_b64(score_ghost.json().get("image_b64", "")),
            "score ghost image is a PNG",
        )
        add_check(
            checks,
            errors,
            "seed_score_ghost_includes_stroke_log",
            is_replayable_stroke_log(score_ghost_log),
            "seed score ghost exposes replayable strokes",
        )
    if efficiency_ghost.status_code == 200:
        efficiency_ghost_log = efficiency_ghost.json().get("stroke_log")
        add_check(
            checks,
            errors,
            "seed_efficiency_ghost_includes_stroke_log",
            is_replayable_stroke_log(efficiency_ghost_log),
            "seed efficiency ghost exposes replayable strokes",
        )

    drawing = build_replayable_submission(
        pair_id=daily_body["pair_id"],
        pairs_path=Path(os.environ["GITAI_PAIRS_PATH"]),
    )
    score_first = client.post(
        "/v1/score",
        json={
            "image_b64": drawing["image_b64"],
            "pair_id": daily_body["pair_id"],
            "ref_version": daily_body["ref_version"],
            "stroke_log": drawing["stroke_log"],
        },
    )
    score_second = client.post(
        "/v1/score",
        json={
            "image_b64": drawing["image_b64"],
            "pair_id": daily_body["pair_id"],
            "ref_version": daily_body["ref_version"],
            "stroke_log": drawing["stroke_log"],
        },
    )
    deterministic = (
        score_first.status_code == 200
        and score_second.status_code == 200
        and stable_score(score_first.json()) == stable_score(score_second.json())
    )
    add_check(checks, errors, "pre_submit_score_is_deterministic", deterministic, response_detail(score_first))

    submission = client.post(
        "/v1/submissions",
        json={
            "image_b64": drawing["image_b64"],
            "pair_id": daily_body["pair_id"],
            "ref_version": daily_body["ref_version"],
            "puzzle_date": daily_body["date"],
            "user_id": "first-player",
            "display_name": "first player",
            "friend_code": "smoke",
            "stroke_log": drawing["stroke_log"],
        },
    )
    add_response_check(checks, errors, "submission_accepts_replayable_drawing", submission)
    if submission.status_code != 200:
        return
    submission_body = submission.json()
    submission_id = submission_body["submission_id"]
    report["submission"] = {
        "submission_id": submission_id,
        "score": submission_body["score"],
        "percentile": submission_body["percentile"],
        "rank": submission_body["rank"],
        "bucket": submission_body["bucket"],
        "reward_count": len(submission_body.get("rewards", [])),
    }

    score_board = client.get(f"/v1/leaderboard?date={daily_body['date']}&kind=score")
    friend_board = client.get(f"/v1/leaderboard?date={daily_body['date']}&kind=friend&friend_code=smoke")
    add_response_check(checks, errors, "score_leaderboard_loads_after_submit", score_board)
    add_response_check(checks, errors, "friend_leaderboard_loads_after_submit", friend_board)
    if friend_board.status_code == 200:
        friend_ids = [item["submission_id"] for item in friend_board.json().get("entries", [])]
        add_check(checks, errors, "friend_ladder_contains_player", submission_id in friend_ids, str(friend_ids))
    friend_ghost = client.get(f"/v1/ghost?date={daily_body['date']}&kind=friend&friend_code=smoke")
    add_response_check(checks, errors, "friend_ghost_loads_after_submit", friend_ghost)
    if friend_ghost.status_code == 200:
        ghost_log = friend_ghost.json().get("stroke_log")
        add_check(
            checks,
            errors,
            "friend_ghost_includes_stroke_log",
            isinstance(ghost_log, dict) and bool(ghost_log.get("strokes")),
            "friend ghost exposes replayable strokes",
        )

    card = client.get(f"/v1/share-card?submission_id={submission_id}")
    add_check(
        checks,
        errors,
        "share_card_generates_png",
        card.status_code == 200 and card.content.startswith(b"\x89PNG\r\n\x1a\n"),
        response_detail(card),
    )

    vote = client.post("/v1/funny-votes", json={"submission_id": submission_id, "user_id": "first-viewer"})
    add_response_check(checks, errors, "funny_vote_accepts_viewer", vote)
    funny_board = client.get(f"/v1/leaderboard?date={daily_body['date']}&kind=funny")
    add_response_check(checks, errors, "funny_ladder_loads", funny_board)

    report_response = client.post(
        "/v1/content-reports",
        json={"submission_id": submission_id, "user_id": "safety-viewer", "reason": "unsafe"},
    )
    add_response_check(checks, errors, "content_report_records_submission", report_response)
    if report_response.status_code == 200:
        add_check(
            checks,
            errors,
            "content_report_has_review_counter",
            report_response.json().get("report_count") == 1,
            str(report_response.json().get("status", "")),
        )

    appraisal = client.post(
        "/v1/appraisal-comments",
        json={"submission_id": submission_id, "user_id": "first-player", "mode": "on_demand"},
    )
    add_response_check(checks, errors, "appraiser_comment_falls_back_safely", appraisal)
    if appraisal.status_code == 200:
        add_check(
            checks,
            errors,
            "appraiser_comment_has_line",
            bool(appraisal.json().get("comment", {}).get("line")),
            appraisal.json().get("status", ""),
        )

    redeem = client.post("/v1/premium/redeem", json={"user_id": "first-player", "code": "SMOKEPASS"})
    premium_after = client.get("/v1/premium?user_id=first-player")
    add_response_check(checks, errors, "premium_code_redeems", redeem)
    add_check(
        checks,
        errors,
        "premium_status_updates",
        premium_after.status_code == 200 and premium_after.json().get("premium") is True,
        response_detail(premium_after),
    )

    proposal = client.post(
        "/v1/pair-proposals",
        json={
            "user_id": "first-player",
            "base_label": daily_body["base"]["canonical_label"],
            "target_label": daily_body["target"]["canonical_label"],
        },
    )
    add_response_check(checks, errors, "pair_proposal_accepts_current_labels", proposal)
    if proposal.status_code == 200:
        proposal_body = proposal.json()
        report["proposal"] = {
            "proposal_id": proposal_body["proposal_id"],
            "status": proposal_body["status"],
            "support_count": proposal_body["support_count"],
        }
        add_check(
            checks,
            errors,
            "pair_proposal_is_reviewable",
            proposal_body["status"] in {"candidate", "needs_catalog_review", "approved"},
            proposal_body["status"],
        )

    smoke_archived_daily_submissions(client, archive_entries, report, checks, errors)


def smoke_archived_daily_submissions(
    client: TestClient,
    archive_entries: list[dict[str, Any]],
    report: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> None:
    failed: list[str] = []
    summaries: list[dict[str, Any]] = []
    for index, entry in enumerate(archive_entries):
        entry_date = str(entry.get("date", ""))
        daily = client.get(f"/v1/daily-puzzle?date={entry_date}")
        if daily.status_code != 200:
            failed.append(f"{entry_date}: {response_detail(daily)}")
            continue
        daily_body = daily.json()
        drawing = build_replayable_submission(
            pair_id=daily_body["pair_id"],
            pairs_path=Path(os.environ["GITAI_PAIRS_PATH"]),
        )
        submission = client.post(
            "/v1/submissions",
            json={
                "image_b64": drawing["image_b64"],
                "pair_id": daily_body["pair_id"],
                "ref_version": daily_body["ref_version"],
                "puzzle_date": daily_body["date"],
                "user_id": f"archive-player-{index}",
                "display_name": f"archive {index + 1}",
                "friend_code": "archive",
                "stroke_log": drawing["stroke_log"],
            },
        )
        if submission.status_code != 200:
            failed.append(f"{entry_date}: {response_detail(submission)}")
            continue
        body = submission.json()
        summaries.append(
            {
                "date": daily_body["date"],
                "pair_id": daily_body["pair_id"],
                "base": daily_body["base"]["object_id"],
                "submission_id": body["submission_id"],
                "score": body["score"],
                "percentile": body["percentile"],
            }
        )
    report["archived_submissions"] = summaries
    add_check(
        checks,
        errors,
        "archived_daily_submissions_accept_replayable_drawings",
        not failed,
        "; ".join(failed) if failed else f"{len(summaries)} archived DailyPuzzle submissions accepted",
    )


def build_replayable_submission(pair_id: str, pairs_path: Path) -> dict[str, Any]:
    pair = PairRepository(pairs_path).get(pair_id)
    stroke_log = {
        "strokes": [
            {
                "color": "#fffdf7",
                "size": 54,
                "mode": "draw",
                "points": [
                    {"x": 286, "y": 284, "t": 0, "pressure": 0.5},
                    {"x": 340, "y": 284, "t": 1, "pressure": 0.5},
                    {"x": 394, "y": 284, "t": 2, "pressure": 0.5},
                    {"x": 448, "y": 284, "t": 3, "pressure": 0.5},
                    {"x": 286, "y": 338, "t": 4, "pressure": 0.5},
                    {"x": 340, "y": 338, "t": 5, "pressure": 0.5},
                    {"x": 394, "y": 338, "t": 6, "pressure": 0.5},
                    {"x": 448, "y": 338, "t": 7, "pressure": 0.5},
                    {"x": 286, "y": 392, "t": 8, "pressure": 0.5},
                    {"x": 340, "y": 392, "t": 9, "pressure": 0.5},
                    {"x": 394, "y": 392, "t": 10, "pressure": 0.5},
                    {"x": 448, "y": 392, "t": 11, "pressure": 0.5},
                ],
            },
            {
                "color": "#d7472f",
                "size": 18,
                "mode": "draw",
                "points": [
                    {"x": 302, "y": 258, "t": 1, "pressure": 0.5},
                    {"x": 284, "y": 322, "t": 2, "pressure": 0.5},
                    {"x": 302, "y": 390, "t": 3, "pressure": 0.5},
                ],
            },
            {
                "color": "#d7472f",
                "size": 18,
                "mode": "draw",
                "points": [
                    {"x": 466, "y": 258, "t": 4, "pressure": 0.5},
                    {"x": 484, "y": 322, "t": 5, "pressure": 0.5},
                    {"x": 466, "y": 390, "t": 6, "pressure": 0.5},
                ],
            },
        ]
    }
    parsed = parse_stroke_log(stroke_log, max_strokes=250, max_points_per_stroke=2000)
    if parsed is None:
        raise ValueError("first-play smoke stroke log is not replayable")
    image = render_replay(pair=pair, strokes=parsed, size=(768, 768))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return {
        "image_b64": b64encode(buf.getvalue()).decode("ascii"),
        "stroke_log": stroke_log,
    }


def add_response_check(
    checks: list[dict[str, Any]],
    errors: list[str],
    name: str,
    response,
) -> None:
    add_check(checks, errors, name, response.status_code == 200, response_detail(response))


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


def latest_daily_date(daily_puzzles_path: Path) -> str:
    dates = [item.date for item in DailyPuzzleRepository(daily_puzzles_path).list()]
    return max(dates).isoformat() if dates else date.today().isoformat()


def stable_score(payload: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(payload)
    copied.pop("computed_at", None)
    return copied


def is_png_b64(value: str) -> bool:
    if not value:
        return False
    try:
        return b64decode(value).startswith(b"\x89PNG\r\n\x1a\n")
    except Exception:
        return False


def has_security_headers(response) -> bool:
    return (
        "default-src 'self'" in response.headers.get("content-security-policy", "")
        and "object-src 'none'" in response.headers.get("content-security-policy", "")
        and response.headers.get("x-content-type-options") == "nosniff"
        and response.headers.get("x-frame-options") == "DENY"
        and response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        and "camera=()" in response.headers.get("permissions-policy", "")
        and response.headers.get("cache-control") == "no-store"
    )


def is_replayable_stroke_log(value: Any) -> bool:
    parsed = parse_stroke_log(value if isinstance(value, dict) else None, max_strokes=250, max_points_per_stroke=2000)
    return parsed is not None and bool(parsed)


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


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "first_play_api.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "first_play_api.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# First-play API smoke",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- season_id: `{report['season_id']}`",
        f"- today: `{report['today']}`",
        f"- pair_id: `{summary.get('pair_id', '')}`",
        f"- submission_id: `{summary.get('submission_id', '')}`",
        f"- score: `{summary.get('score', 0)}`",
        f"- percentile: `{summary.get('percentile', 0.0)}`",
        f"- passed_checks: `{summary.get('passed_checks', 0)}`",
        f"- failed_checks: `{summary.get('failed_checks', 0)}`",
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
