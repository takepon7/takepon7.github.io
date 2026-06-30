from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, pstdev

from PIL import Image

from gitai_phase0.reporting import load_cases
from gitai_phase0.repositories import image_fingerprint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "scoring"
PHASE0_CASES = ROOT / "data" / "phase0" / "cases.json"
PHASE0_IMAGES = ROOT / "data" / "phase0" / "images"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = load_cases(PHASE0_CASES)
    pair = cases[0].pair
    write_json(OUT / "pairs.json", {"pairs": [pair_to_dict(pair)]})
    write_json(OUT / "seed_scores.json", {"seed_scores": build_seed_scores(pair.pair_id)})
    write_json(OUT / "ocr_fixtures.json", {"fixtures": build_ocr_fixtures(cases)})
    print(f"Wrote Phase 1 fixtures to {OUT}")


def build_seed_scores(pair_id: str) -> list[dict]:
    refs = []
    sources = [
        ("reports/phase0/results.csv", "heuristic-color-shape-v1", "phase0-heuristic-tau30-2026-06-29"),
        ("reports/phase0_open_clip/results.csv", "open_clip:ViT-L-14:openai:fp32", "phase0-open-clip-tau30-2026-06-29"),
        (
            "reports/phase0_siglip/results.csv",
            "siglip:google/siglip-base-patch16-224:fp32",
            "phase0-siglip-tau30-2026-06-29",
        ),
    ]
    for rel_path, model_version, ref_version in sources:
        path = ROOT / rel_path
        if not path.exists():
            continue
        scores = sorted(
            float(row["raw"])
            for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())
            if float(row["tau"]) == 30.0 and row["expected_quality"] != "attack"
        )
        refs.append(
            {
                "ref_version": ref_version,
                "pair_id": pair_id,
                "model_version": model_version,
                "template_set_id": "drawing_v1",
                "tau": 30.0,
                "scores_sorted": scores,
                "stats": stats(scores),
            }
        )
    return refs


def build_ocr_fixtures(cases) -> list[dict]:
    fixtures = []
    for case in cases:
        if not case.known_text:
            continue
        image = Image.open(PHASE0_IMAGES / case.image_path)
        fixtures.append(
            {
                "case_id": case.case_id,
                "fingerprint": image_fingerprint(image),
                "text": list(case.known_text),
            }
        )
    return fixtures


def stats(scores: list[float]) -> dict[str, float]:
    if not scores:
        return {}
    return {
        "min": min(scores),
        "p10": percentile(scores, 0.10),
        "p50": percentile(scores, 0.50),
        "p90": percentile(scores, 0.90),
        "max": max(scores),
        "mean": mean(scores),
        "std": pstdev(scores),
    }


def percentile(scores: list[float], q: float) -> float:
    if len(scores) == 1:
        return scores[0]
    index = q * (len(scores) - 1)
    lower = int(index)
    upper = min(lower + 1, len(scores) - 1)
    weight = index - lower
    return scores[lower] * (1.0 - weight) + scores[upper] * weight


def pair_to_dict(pair) -> dict:
    return {
        "pair_id": pair.pair_id,
        "base": object_to_dict(pair.base),
        "target": object_to_dict(pair.target),
        "hard_negatives": [object_to_dict(item) for item in pair.hard_negatives],
    }


def object_to_dict(obj) -> dict:
    return {
        "object_id": obj.object_id,
        "canonical_label": obj.canonical_label,
        "aliases": list(obj.aliases),
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
