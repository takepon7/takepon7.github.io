from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gitai_phase0.drawing_verification import SUPPORTED_BASE_RENDERER_IDS  # noqa: E402


def main() -> None:
    source_ts = (ROOT / "web" / "src" / "main.ts").read_text(encoding="utf-8")
    html = (ROOT / "web" / "dist" / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r'src="([^"]+\.js)"', html)
    styles = re.findall(r'href="([^"]+\.css)"', html)
    assert scripts, "built index.html must reference a JavaScript bundle"
    assert styles, "built index.html must reference a CSS bundle"

    js_text = "\n".join((ROOT / "web" / "dist" / script.lstrip("/")).read_text(encoding="utf-8") for script in scripts)
    css_text = "\n".join((ROOT / "web" / "dist" / style.lstrip("/")).read_text(encoding="utf-8") for style in styles)

    required_runtime_tokens = [
        "/v1/daily-puzzle",
        "/v1/daily-puzzles",
        "/v1/submissions",
        "/v1/leaderboard",
        "/v1/ghost",
        "/v1/share-card",
        "/v1/funny-votes",
        "/v1/appraisal-comments",
        "/v1/cosmetics",
        "/v1/premium",
        "/v1/premium/redeem",
        "/v1/pair-proposals",
        "efficiency-tab",
        "friend-tab",
        "funny-tab",
        "share-friend-code",
        "premium-badge",
        "premium-code",
        "redeem-premium",
        "daily-select",
        "gitai.dailyDate",
        "friend_code",
        "season_id",
        "season-label",
        "palette-select",
        "replay-button",
        "Replay",
        "再生中",
        "locked",
        "newly_unlocked",
        "funny_votes",
        "comment",
        "mood",
        "percentile",
        "share-percentile",
        "daily_spend",
        "fallback_hero_gate",
        "mode",
        "hero",
        "特別鑑定中",
        "circle",
        "stroke_log",
        "leaderboard-list",
        "Efficiency",
        "Friends",
        "Funny",
        "Appraiser",
        "Top Ghost",
        "ghost-replay-button",
        "ghost-replay-canvas",
        "stroke_log",
        "navigator.share",
        "navigator.canShare",
        "gitai-share-card.png",
        "Top --",
        "Next Pair",
        "proposal-button",
        "support_count",
        "候補入り",
        "レビュー待ち",
        "提出画像を再生できません",
        "本日の挑戦回数",
        "まだ鑑定前です",
        "privacy-link",
        "terms-link",
        "safety-link",
        "/privacy.html",
        "/terms.html",
        "/safety.html",
    ]
    required_style_tokens = [
        ".draw-canvas",
        ".draw-canvas.locked",
        ".share-card",
        ".share-percentile",
        ".share-action",
        ".leaderboard-row",
        ".ghost-card",
        ".ghost-vote",
        ".ghost-replay",
        ".ghost-replay-canvas",
        ".friend-input",
        ".friend-code-button",
        ".pass-input",
        ".pass-badge",
        ".pair-proposal",
        ".proposal-row",
        ".proposal-button",
        ".daily-select",
        ".palette-select",
        ".policy-links",
        ".segment",
        "@media",
        ".scan-line",
    ]

    missing_runtime = [token for token in required_runtime_tokens if token not in js_text]
    missing_styles = [token for token in required_style_tokens if token not in css_text]
    production_localhost_tokens = [
        token
        for token in ("http://127.0.0.1:8000", "http://localhost:8000")
        if token in js_text
    ]
    required_html_tokens = [
        "AIをだます擬態ドローイングゲーム",
        'property="og:image"',
        "/brand/og-image.png",
        'name="twitter:card"',
        "/site.webmanifest",
        "/brand/favicon-32.png",
        "/brand/apple-touch-icon.png",
    ]
    missing_html = [token for token in required_html_tokens if token not in html]
    public_assets = [
        ROOT / "web" / "dist" / "brand" / "og-image.png",
        ROOT / "web" / "dist" / "brand" / "marketing-hero-16x9.png",
        ROOT / "web" / "dist" / "brand" / "social-feed-square.png",
        ROOT / "web" / "dist" / "brand" / "social-story-vertical.png",
        ROOT / "web" / "dist" / "brand" / "share-card-examples.json",
        ROOT / "web" / "dist" / "brand" / "app-icon-192.png",
        ROOT / "web" / "dist" / "brand" / "app-icon-512.png",
        ROOT / "web" / "dist" / "brand" / "apple-touch-icon.png",
        ROOT / "web" / "dist" / "brand" / "favicon-32.png",
        ROOT / "web" / "dist" / "site.webmanifest",
        ROOT / "web" / "dist" / "robots.txt",
        ROOT / "web" / "dist" / "privacy.html",
        ROOT / "web" / "dist" / "terms.html",
        ROOT / "web" / "dist" / "safety.html",
    ]
    missing_public_assets = [str(path) for path in public_assets if not path.exists()]
    client_base_ids = set(re.findall(r'objectId === "([^"]+)"', source_ts))
    daily_base_ids = daily_base_object_ids()
    missing_replay_base_renderers = sorted((client_base_ids | daily_base_ids) - SUPPORTED_BASE_RENDERER_IDS)
    clear_preserves_base = bool(
        re.search(
            r'clearTool\.addEventListener\("click",\s*\(\) => \{.*resetToBase\(\);.*\}\);',
            source_ts,
            re.S,
        )
    )
    undo_preserves_base = bool(
        re.search(r"function redrawAll\(\): void \{\s*paintBaseLayer\(\);", source_ts, re.S)
    )
    replay_uses_strokes = bool(
        re.search(r"async function replayDrawing\(\): Promise<void> \{.*cloneStrokes\(strokes\)", source_ts, re.S)
    )
    replay_locks_canvas = '"locked"' in source_ts and "setDrawingControlsDisabled(true)" in source_ts
    assert not missing_runtime, f"missing runtime tokens: {missing_runtime}"
    assert not missing_styles, f"missing style tokens: {missing_styles}"
    assert not production_localhost_tokens, (
        "production bundle must not default to localhost API: "
        f"{production_localhost_tokens}"
    )
    assert not missing_html, f"missing publish metadata tokens: {missing_html}"
    assert not missing_public_assets, f"missing public assets: {missing_public_assets}"
    assert not missing_replay_base_renderers, (
        "missing replay base renderers: "
        f"{missing_replay_base_renderers}"
    )
    assert clear_preserves_base, "clear tool must reset to the base object, not a blank canvas"
    assert undo_preserves_base, "undo redraw must start from the base object, not a blank canvas"
    assert replay_uses_strokes, "replay must use the current stroke log"
    assert replay_locks_canvas, "replay/judging must lock the canvas while running"

    payload = {
        "html": str(ROOT / "web" / "dist" / "index.html"),
        "scripts": scripts,
        "styles": styles,
        "client_base_ids": sorted(client_base_ids),
        "daily_base_ids": sorted(daily_base_ids),
        "replay_base_ids": sorted(SUPPORTED_BASE_RENDERER_IDS),
        "missing_replay_base_renderers": missing_replay_base_renderers,
        "public_assets": [str(path) for path in public_assets],
        "checks": {
            "daily_puzzle_fetch": True,
            "daily_puzzle_archive_fetch": True,
            "daily_puzzle_picker": True,
            "season_boundary_fetch": True,
            "submission_post": True,
            "daily_submission_limit_message": True,
            "leaderboard_fetch": True,
            "leaderboard_percentile_display": True,
            "efficiency_ladder_toggle": True,
            "friend_ladder_toggle": True,
            "funny_ladder_toggle": True,
            "funny_vote_submission": True,
            "template_bank_comment": True,
            "appraiser_comment_request": True,
            "hero_appraiser_comment_request": True,
            "cosmetic_palette_fetch": True,
            "premium_pass_redeem": True,
            "pair_proposal_submission": True,
            "ghost_fetch": True,
            "ghost_replay_surface": True,
            "ghost_stroke_log_consumption": True,
            "stroke_log_submission": True,
            "stroke_replay_button": True,
            "stroke_replay_locks_canvas": True,
            "responsive_css": True,
            "share_card_surface": True,
            "share_card_native_share": True,
            "share_percentile_surface": True,
            "share_card_endpoint": True,
            "result_percentile_display": True,
            "client_replay_base_parity": True,
            "client_clear_preserves_base": clear_preserves_base,
            "client_undo_preserves_base": undo_preserves_base,
            "client_replay_uses_strokes": replay_uses_strokes,
            "client_canvas_locks_while_busy": replay_locks_canvas,
            "publish_metadata": True,
            "publish_brand_assets": True,
            "publish_legal_pages": True,
            "production_api_base_not_localhost": True,
        },
    }
    out = ROOT / "reports" / "phase3_static_smoke.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload["checks"], indent=2, sort_keys=True))
    print(f"Wrote {out}")


def daily_base_object_ids() -> set[str]:
    pairs_payload = json.loads((ROOT / "data" / "scoring" / "pairs.json").read_text(encoding="utf-8"))
    daily_payload = json.loads((ROOT / "data" / "puzzle" / "daily_puzzles.json").read_text(encoding="utf-8"))
    pairs_by_id = {str(item["pair_id"]): item for item in pairs_payload.get("pairs", [])}
    base_ids: set[str] = set()
    for item in daily_payload.get("daily_puzzles", []):
        pair = pairs_by_id.get(str(item.get("pair_id")))
        if pair:
            base_ids.add(str(pair["base"]["object_id"]))
    return base_ids


if __name__ == "__main__":
    main()
