from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path

from gitai_phase0.puzzle import (
    CurationPolicy,
    PuzzleQuality,
    freeze_daily_puzzle,
    generate_candidate_pairs,
)
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository
from gitai_phase0.repositories import SeedScoreRepository

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "puzzle" / "object_catalog.json"
SEED_SCORES = ROOT / "data" / "scoring" / "seed_scores.json"
OUT_DIR = ROOT / "data" / "puzzle"
REPORTS = ROOT / "reports"
DEFAULT_REF_VERSION = "phase0-open-clip-tau30-2026-06-29"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    objects = ObjectCatalogRepository(CATALOG).list()
    seed_refs = SeedScoreRepository(SEED_SCORES).list()
    policy = CurationPolicy()
    candidates = generate_candidate_pairs(objects, policy)
    qualities = [policy.evaluate_seed_scores(ref) for ref in seed_refs]
    quality_by_pair = accepted_quality_by_pair(
        qualities,
        preferred_ref_version=os.environ.get("GITAI_PHASE2_REF_VERSION", DEFAULT_REF_VERSION),
    )

    daily_puzzle = freeze_daily_puzzle(
        puzzle_date=date(2026, 6, 29),
        eligible_pairs=candidates,
        qualities=quality_by_pair,
        frozen_at=datetime(2026, 6, 29, 0, 0, 0, tzinfo=timezone.utc),
    )

    write_json(
        OUT_DIR / "pair_candidates.json",
        {"pairs": [candidate.to_dict() for candidate in candidates]},
    )
    write_json(
        OUT_DIR / "measured_quality.json",
        {"qualities": [quality_to_dict(item) for item in qualities]},
    )
    write_json(
        OUT_DIR / "daily_puzzles.json",
        {"daily_puzzles": [daily_puzzle.to_dict()]},
    )
    write_report(REPORTS / "phase2_puzzle_pool.md", objects, candidates, qualities)
    print(f"Wrote Phase 2 puzzle pool fixtures to {OUT_DIR}")


def accepted_quality_by_pair(
    qualities: list[PuzzleQuality],
    preferred_ref_version: str,
) -> dict[str, PuzzleQuality]:
    accepted = [item for item in qualities if item.accepted]
    chosen: dict[str, PuzzleQuality] = {}
    for quality in accepted:
        if quality.ref_version == preferred_ref_version:
            chosen[quality.pair_id] = quality
    for quality in sorted(accepted, key=lambda item: (-item.spread, item.ref_version)):
        chosen.setdefault(quality.pair_id, quality)
    return chosen


def quality_to_dict(quality: PuzzleQuality) -> dict:
    return {
        "ref_version": quality.ref_version,
        "pair_id": quality.pair_id,
        "spread": quality.spread,
        "p10": quality.p10,
        "p50": quality.p50,
        "p90": quality.p90,
        "accepted": quality.accepted,
        "measured_difficulty": quality.measured_difficulty,
        "rejection_reasons": list(quality.rejection_reasons),
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_report(path: Path, objects, candidates, qualities: list[PuzzleQuality]) -> None:
    accepted = [quality for quality in qualities if quality.accepted]
    lines = [
        "# Phase 2 Puzzle Pool",
        "",
        f"- catalog_objects: `{len(objects)}`",
        f"- plausible_candidate_pairs: `{len(candidates)}`",
        f"- measured_seed_refs: `{len(qualities)}`",
        f"- accepted_measured_refs: `{len(accepted)}`",
        "",
        "## Measured Qualities",
        "",
        "| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for quality in sorted(qualities, key=lambda item: item.ref_version):
        lines.append(
            "| "
            + " | ".join(
                [
                    quality.ref_version,
                    quality.pair_id,
                    str(quality.accepted).lower(),
                    f"{quality.spread:.4f}",
                    f"{quality.p10:.4f}",
                    f"{quality.p50:.4f}",
                    f"{quality.p90:.4f}",
                    quality.measured_difficulty,
                    ", ".join(quality.rejection_reasons) or "-",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "Not complete. The funnel is implemented, but the Phase 2 gate requires dozens of measured pairs. This run only has the Phase 0 `apple -> baseball` seed distribution.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
