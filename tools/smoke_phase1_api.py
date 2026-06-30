from __future__ import annotations

from base64 import b64encode
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from gitai_phase0.api import create_app

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "data" / "phase0" / "images"
REPORTS = ROOT / "reports"

REF_BY_MODEL = {
    "heuristic": "phase0-heuristic-tau30-2026-06-29",
    "open_clip": "phase0-open-clip-tau30-2026-06-29",
    "siglip": "phase0-siglip-tau30-2026-06-29",
}


def main() -> None:
    model = os.environ.get("GITAI_MODEL", "heuristic")
    ref_version = os.environ.get("GITAI_REF_VERSION", REF_BY_MODEL[model])
    client = TestClient(create_app())

    samples = {
        "plain": post_score(client, "apple_plain.png", ref_version),
        "good": post_score(client, "apple_baseball_good.png", ref_version),
        "attack": post_score(client, "apple_baseball_text_attack.png", ref_version),
    }
    repeat = post_score(client, "apple_baseball_good.png", ref_version)
    assert stable(samples["good"]) == stable(repeat)
    assert samples["good"]["raw"] > samples["plain"]["raw"]
    assert samples["good"]["score"] > samples["plain"]["score"]
    assert samples["attack"]["raw"] == 0.0
    assert samples["attack"]["flags"]["ocr_cheat"] is True

    payload = {
        "model": model,
        "ref_version": ref_version,
        "samples": samples,
        "checks": {
            "deterministic_repeat": True,
            "good_above_plain": True,
            "text_attack_zeroed": True,
        },
    }
    out_path = REPORTS / f"phase1_api_smoke_{model}.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload["checks"], indent=2, sort_keys=True))
    print(f"Wrote {out_path}")


def post_score(client: TestClient, filename: str, ref_version: str) -> dict:
    image_b64 = b64encode((IMAGES / filename).read_bytes()).decode("ascii")
    response = client.post(
        "/v1/score",
        json={
            "image_b64": image_b64,
            "pair_id": "apple_to_baseball",
            "ref_version": ref_version,
        },
    )
    response.raise_for_status()
    return response.json()


def stable(response: dict) -> dict:
    copied = dict(response)
    copied.pop("computed_at", None)
    return copied


if __name__ == "__main__":
    main()
