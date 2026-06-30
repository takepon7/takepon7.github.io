from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from gitai_phase0.api import build_state_from_env, create_app

try:
    from tools.smoke_first_play_api import build_replayable_submission, patched_env
except ModuleNotFoundError:
    from smoke_first_play_api import build_replayable_submission, patched_env


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "web" / "public" / "brand" / "share-cards"
DEFAULT_MANIFEST = ROOT / "web" / "public" / "brand" / "share-card-examples.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public marketing share-card examples from real API output.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--today", default="2026-07-06")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    manifest = build_marketing_share_cards(
        out_dir=args.out_dir,
        manifest_path=args.manifest,
        today=args.today,
        limit=args.limit,
    )
    print(f"Wrote {args.manifest}")
    print(f"Wrote {len(manifest['examples'])} share cards to {args.out_dir}")


def build_marketing_share_cards(
    out_dir: Path = DEFAULT_OUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
    today: str = "2026-07-06",
    limit: int = 5,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old_card in out_dir.glob("share-card-example-*.png"):
        old_card.unlink()

    with tempfile.TemporaryDirectory(prefix="gitai-marketing-cards-") as tmpdir:
        tmp = Path(tmpdir)
        env = {
            "GITAI_RUNTIME_DB": str(tmp / "runtime.sqlite"),
            "GITAI_IMAGE_STORE": str(tmp / "submissions"),
            "GITAI_MODEL": "heuristic",
            "GITAI_OCR": "fingerprint",
            "GITAI_MODERATION": "fingerprint",
            "GITAI_TODAY": today,
            "GITAI_LAYER2_ACTOR": "null",
            "GITAI_DAILY_SUBMISSION_LIMIT": str(max(limit + 5, 10)),
            "GITAI_PUBLIC_WEB_URL": "gitai",
        }
        with patched_env(env, remove=("GITAI_DAILY_REF_VERSION", "GITAI_SEASON_MODEL_VERSION")):
            client = TestClient(create_app(build_state_from_env()))
            archive = client.get("/v1/daily-puzzles")
            archive.raise_for_status()
            examples = build_examples(client, archive.json().get("entries", [])[:limit], out_dir)

    manifest = {
        "generated_from": "tools/build_marketing_share_cards.py",
        "today": today,
        "examples": examples,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_examples(client: TestClient, entries: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        date_value = str(entry["date"])
        daily = client.get(f"/v1/daily-puzzle?date={date_value}")
        daily.raise_for_status()
        daily_body = daily.json()
        drawing = build_replayable_submission(
            pair_id=daily_body["pair_id"],
            pairs_path=Path(os.environ.get("GITAI_PAIRS_PATH", "data/scoring/pairs.json")),
        )
        submission = client.post(
            "/v1/submissions",
            json={
                "image_b64": drawing["image_b64"],
                "pair_id": daily_body["pair_id"],
                "ref_version": daily_body["ref_version"],
                "puzzle_date": daily_body["date"],
                "user_id": f"marketing-player-{index}",
                "display_name": f"launch {index}",
                "friend_code": "launch",
                "stroke_log": drawing["stroke_log"],
            },
        )
        submission.raise_for_status()
        submission_body = submission.json()
        card = client.get(f"/v1/share-card?submission_id={submission_body['submission_id']}")
        card.raise_for_status()
        filename = f"share-card-example-{date_value}-{daily_body['pair_id']}.png"
        path = out_dir / filename
        path.write_bytes(card.content)
        with Image.open(path) as image:
            size = image.size
        examples.append(
            {
                "date": date_value,
                "pair_id": daily_body["pair_id"],
                "base": daily_body["base"]["canonical_label"],
                "target": daily_body["target"]["canonical_label"],
                "score": submission_body["score"],
                "percentile": submission_body["percentile"],
                "path": f"web/public/brand/share-cards/{filename}",
                "size": list(size),
            }
        )
    return examples


if __name__ == "__main__":
    main()
