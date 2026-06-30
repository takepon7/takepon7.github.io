from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from gitai_phase0.repositories import SeedScoreRef

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAIRS = ROOT / "data" / "scoring" / "pairs.json"
DEFAULT_SEED_SCORES = ROOT / "data" / "scoring" / "seed_scores.json"
DEFAULT_DRAFT_PAIRS = ROOT / "data" / "puzzle" / "approved_seed_asset_pack" / "approved_seed_pairs.json"
DEFAULT_DRAFT_SEED_SCORES = ROOT / "reports" / "phase2" / "approved_seed_scores" / "approved_seed_scores.json"
DEFAULT_MEASURED_QUALITY = ROOT / "reports" / "phase2" / "approved_seed_scores" / "approved_measured_quality.json"
DEFAULT_OUT_DIR = ROOT / "reports" / "phase2" / "seed_score_promotion"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote accepted approved SeedScores drafts into canonical scoring data."
    )
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--seed-scores", type=Path, default=DEFAULT_SEED_SCORES)
    parser.add_argument("--draft-pairs", type=Path, default=DEFAULT_DRAFT_PAIRS)
    parser.add_argument("--draft-seed-scores", type=Path, default=DEFAULT_DRAFT_SEED_SCORES)
    parser.add_argument("--measured-quality", type=Path, default=DEFAULT_MEASURED_QUALITY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--allow-rejected", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = promote_seed_scores(
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        draft_pairs_path=args.draft_pairs,
        draft_seed_scores_path=args.draft_seed_scores,
        measured_quality_path=args.measured_quality,
        out_dir=args.out_dir,
        apply=args.apply,
        allow_rejected=args.allow_rejected,
    )
    mode = "applied" if report["applied"] else "preview"
    print(f"Wrote {args.out_dir / 'promotion_report.json'}")
    print(f"Wrote {args.out_dir / 'promotion_report.md'}")
    print(f"Wrote {args.out_dir / 'merged_pairs.json'}")
    print(f"Wrote {args.out_dir / 'merged_seed_scores.json'}")
    print(
        f"{mode}: {report['summary']['pairs_added']} pairs, "
        f"{report['summary']['seed_scores_added']} seed score refs"
    )


def promote_seed_scores(
    pairs_path: Path,
    seed_scores_path: Path,
    draft_pairs_path: Path,
    draft_seed_scores_path: Path,
    measured_quality_path: Path,
    out_dir: Path,
    apply: bool = False,
    allow_rejected: bool = False,
) -> dict[str, Any]:
    canonical_pairs = load_json(pairs_path)
    canonical_seed_scores = load_json(seed_scores_path)
    draft_pairs = load_json(draft_pairs_path)
    draft_seed_scores = load_json(draft_seed_scores_path)
    measured_quality = load_json(measured_quality_path)

    merged_pairs = deepcopy(canonical_pairs)
    merged_seed_scores = deepcopy(canonical_seed_scores)
    report = {
        "applied": apply,
        "allow_rejected": allow_rejected,
        "pairs": [],
        "seed_scores": [],
        "errors": [],
        "summary": {
            "pairs_added": 0,
            "pairs_reused": 0,
            "seed_scores_added": 0,
            "seed_scores_reused": 0,
        },
    }

    pair_by_id = {item["pair_id"]: item for item in merged_pairs.get("pairs", [])}
    for draft_pair in draft_pairs.get("pairs", []):
        pair_id = str(draft_pair["pair_id"])
        existing = pair_by_id.get(pair_id)
        if existing is None:
            merged_pairs.setdefault("pairs", []).append(draft_pair)
            pair_by_id[pair_id] = draft_pair
            report["pairs"].append({"pair_id": pair_id, "status": "added"})
            report["summary"]["pairs_added"] += 1
        elif pair_compatible(existing, draft_pair):
            report["pairs"].append({"pair_id": pair_id, "status": "existing_compatible"})
            report["summary"]["pairs_reused"] += 1
        else:
            report["errors"].append(
                {
                    "kind": "pair_conflict",
                    "pair_id": pair_id,
                    "detail": "draft pair does not match existing canonical pair",
                }
            )

    quality_by_ref = {
        str(item["ref_version"]): item
        for item in measured_quality.get("qualities", [])
    }
    seed_score_by_ref = {
        str(item["ref_version"]): item
        for item in merged_seed_scores.get("seed_scores", [])
    }
    for draft_ref in draft_seed_scores.get("seed_scores", []):
        parsed = SeedScoreRef.from_dict(draft_ref)
        quality = quality_by_ref.get(parsed.ref_version)
        if quality is None:
            report["errors"].append(
                {
                    "kind": "missing_quality",
                    "ref_version": parsed.ref_version,
                    "detail": "draft SeedScores ref has no measured quality row",
                }
            )
            continue
        if not bool(quality.get("accepted", False)) and not allow_rejected:
            report["seed_scores"].append(
                {
                    "ref_version": parsed.ref_version,
                    "pair_id": parsed.pair_id,
                    "status": "skipped_rejected_quality",
                    "rejection_reasons": quality.get("rejection_reasons", []),
                }
            )
            continue
        if parsed.pair_id not in pair_by_id:
            report["errors"].append(
                {
                    "kind": "missing_pair",
                    "ref_version": parsed.ref_version,
                    "pair_id": parsed.pair_id,
                    "detail": "draft SeedScores ref references a pair that is not canonical or draft",
                }
            )
            continue
        existing_ref = seed_score_by_ref.get(parsed.ref_version)
        if existing_ref is None:
            merged_seed_scores.setdefault("seed_scores", []).append(draft_ref)
            seed_score_by_ref[parsed.ref_version] = draft_ref
            report["seed_scores"].append(
                {
                    "ref_version": parsed.ref_version,
                    "pair_id": parsed.pair_id,
                    "status": "added",
                }
            )
            report["summary"]["seed_scores_added"] += 1
        elif seed_score_equal(existing_ref, draft_ref):
            report["seed_scores"].append(
                {
                    "ref_version": parsed.ref_version,
                    "pair_id": parsed.pair_id,
                    "status": "existing_identical",
                }
            )
            report["summary"]["seed_scores_reused"] += 1
        else:
            report["errors"].append(
                {
                    "kind": "seed_score_conflict",
                    "ref_version": parsed.ref_version,
                    "detail": "draft SeedScores ref conflicts with existing canonical ref",
                }
            )

    if report["errors"]:
        report["applied"] = False

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "merged_pairs.json", merged_pairs)
    write_json(out_dir / "merged_seed_scores.json", merged_seed_scores)
    write_json(out_dir / "promotion_report.json", report)
    (out_dir / "promotion_report.md").write_text(render_markdown(report), encoding="utf-8")

    if apply and not report["errors"]:
        write_json(pairs_path, merged_pairs)
        write_json(seed_scores_path, merged_seed_scores)

    return report


def pair_compatible(existing: dict[str, Any], draft: dict[str, Any]) -> bool:
    if str(existing.get("pair_id")) != str(draft.get("pair_id")):
        return False
    if not object_label_compatible(existing.get("base", {}), draft.get("base", {})):
        return False
    if not object_label_compatible(existing.get("target", {}), draft.get("target", {})):
        return False
    existing_negs = existing.get("hard_negatives", [])
    draft_negs = draft.get("hard_negatives", [])
    if len(existing_negs) != len(draft_negs):
        return False
    return all(
        object_label_compatible(left, right)
        for left, right in zip(existing_negs, draft_negs)
    )


def object_label_compatible(existing: dict[str, Any], draft: dict[str, Any]) -> bool:
    if str(existing.get("object_id")) != str(draft.get("object_id")):
        return False
    if str(existing.get("canonical_label")) != str(draft.get("canonical_label")):
        return False
    existing_aliases = {str(item) for item in existing.get("aliases", [])}
    draft_aliases = {str(item) for item in draft.get("aliases", [])}
    return draft_aliases.issubset(existing_aliases)


def seed_score_equal(existing: dict[str, Any], draft: dict[str, Any]) -> bool:
    return normalize_json(existing) == normalize_json(draft)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SeedScores promotion report",
        "",
        f"- applied: `{str(report['applied']).lower()}`",
        f"- allow_rejected: `{str(report['allow_rejected']).lower()}`",
        f"- pairs_added: `{report['summary']['pairs_added']}`",
        f"- pairs_reused: `{report['summary']['pairs_reused']}`",
        f"- seed_scores_added: `{report['summary']['seed_scores_added']}`",
        f"- seed_scores_reused: `{report['summary']['seed_scores_reused']}`",
        f"- errors: `{len(report['errors'])}`",
        "",
        "## Pairs",
        "",
        "| pair_id | status |",
        "| --- | --- |",
    ]
    for item in report["pairs"]:
        lines.append(f"| {item['pair_id']} | {item['status']} |")
    lines.extend(["", "## SeedScores", "", "| ref_version | pair_id | status |", "| --- | --- | --- |"])
    for item in report["seed_scores"]:
        lines.append(f"| {item['ref_version']} | {item['pair_id']} | {item['status']} |")
    if report["errors"]:
        lines.extend(["", "## Errors", "", "| kind | id | detail |", "| --- | --- | --- |"])
        for item in report["errors"]:
            identifier = item.get("pair_id") or item.get("ref_version") or "-"
            lines.append(f"| {item['kind']} | {identifier} | {item['detail']} |")
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    main()
