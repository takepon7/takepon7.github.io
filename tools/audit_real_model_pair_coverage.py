from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "real_model_pair_coverage"
HEURISTIC_MODEL = "heuristic-color-shape-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit real-model SeedScore coverage for launch planning.")
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--seed-scores", type=Path, default=ROOT / "data" / "scoring" / "seed_scores.json")
    parser.add_argument("--daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    report = audit_real_model_pair_coverage(
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        daily_puzzles_path=args.daily_puzzles,
        out_dir=args.out_dir,
    )
    print(f"Wrote {args.out_dir / 'real_model_pair_coverage.json'}")
    print(f"Wrote {args.out_dir / 'real_model_pair_coverage.md'}")
    print(f"valid={str(report['valid']).lower()}")
    if not report["valid"]:
        raise SystemExit(1)


def audit_real_model_pair_coverage(
    pairs_path: Path = ROOT / "data" / "scoring" / "pairs.json",
    seed_scores_path: Path = ROOT / "data" / "scoring" / "seed_scores.json",
    daily_puzzles_path: Path = ROOT / "data" / "puzzle" / "daily_puzzles.json",
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    pairs = load_json(pairs_path).get("pairs", [])
    seed_scores = load_json(seed_scores_path).get("seed_scores", [])
    daily_puzzles = load_json(daily_puzzles_path).get("daily_puzzles", [])

    pair_ids = [str(item["pair_id"]) for item in pairs]
    score_by_pair: dict[str, list[dict[str, Any]]] = {pair_id: [] for pair_id in pair_ids}
    for row in seed_scores:
        score_by_pair.setdefault(str(row.get("pair_id", "")), []).append(row)

    real_model_pair_ids = sorted(
        pair_id
        for pair_id in pair_ids
        if any(is_real_model(str(row.get("model_version", ""))) for row in score_by_pair.get(pair_id, []))
    )
    heuristic_only_pair_ids = sorted(pair_id for pair_id in pair_ids if pair_id not in real_model_pair_ids)
    daily_ref_by_version = {str(row.get("ref_version", "")): row for row in seed_scores}
    daily_real_model_refs = [
        item
        for item in daily_puzzles
        if is_real_model(str(daily_ref_by_version.get(str(item.get("ref_version", "")), {}).get("model_version", "")))
    ]
    daily_with_real_model_alternative = [
        item for item in daily_puzzles if str(item.get("pair_id", "")) in real_model_pair_ids
    ]
    expansion_backlog = [
        build_backlog_entry(pair, score_by_pair.get(str(pair["pair_id"]), []))
        for pair in pairs
        if str(pair["pair_id"]) in heuristic_only_pair_ids
    ]
    expansion_backlog.sort(key=lambda item: (item["target"], item["base"], item["pair_id"]))

    report = {
        "valid": True,
        "paths": {
            "pairs": str(pairs_path),
            "seed_scores": str(seed_scores_path),
            "daily_puzzles": str(daily_puzzles_path),
        },
        "summary": {
            "pair_count": len(pair_ids),
            "seed_score_count": len(seed_scores),
            "daily_count": len(daily_puzzles),
            "real_model_pair_count": len(real_model_pair_ids),
            "heuristic_only_pair_count": len(heuristic_only_pair_ids),
            "daily_real_model_ref_count": len(daily_real_model_refs),
            "daily_real_model_alternative_count": len(daily_with_real_model_alternative),
            "expansion_backlog_count": len(expansion_backlog),
        },
        "real_model_pair_ids": real_model_pair_ids,
        "heuristic_only_pair_ids": heuristic_only_pair_ids,
        "daily_real_model_ref_dates": [str(item.get("date", "")) for item in daily_real_model_refs],
        "daily_real_model_alternative_dates": [str(item.get("date", "")) for item in daily_with_real_model_alternative],
        "expansion_backlog": expansion_backlog,
        "recommended_next_actions": [
            "Run SeedAsset scoring for each expansion_backlog pair with open_clip and/or siglip.",
            "Promote accepted real-model SeedScores into data/scoring/seed_scores.json.",
            "Plan future DailyPuzzle entries against real-model ref_versions before a serious public campaign.",
        ],
    }
    write_report(out_dir, report)
    return report


def build_backlog_entry(pair: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    heuristic_refs = [str(row.get("ref_version", "")) for row in rows if not is_real_model(str(row.get("model_version", "")))]
    return {
        "pair_id": str(pair["pair_id"]),
        "base": str(pair.get("base", {}).get("canonical_label", "")),
        "target": str(pair.get("target", {}).get("canonical_label", "")),
        "heuristic_refs": heuristic_refs,
        "recommended_models": [
            "open_clip:ViT-L-14:openai:fp32",
            "siglip:google/siglip-base-patch16-224:fp32",
        ],
    }


def is_real_model(model_version: str) -> bool:
    return bool(model_version) and model_version != HEURISTIC_MODEL and not model_version.startswith("heuristic")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(out_dir: Path, report: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "real_model_pair_coverage.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (out_dir / "real_model_pair_coverage.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Real Model Pair Coverage",
        "",
        f"- valid: `{str(report['valid']).lower()}`",
        f"- pair_count: `{summary['pair_count']}`",
        f"- seed_score_count: `{summary['seed_score_count']}`",
        f"- daily_count: `{summary['daily_count']}`",
        f"- real_model_pair_count: `{summary['real_model_pair_count']}`",
        f"- heuristic_only_pair_count: `{summary['heuristic_only_pair_count']}`",
        f"- daily_real_model_ref_count: `{summary['daily_real_model_ref_count']}`",
        f"- daily_real_model_alternative_count: `{summary['daily_real_model_alternative_count']}`",
        "",
        "## Real-Model Covered Pairs",
        "",
    ]
    if report["real_model_pair_ids"]:
        lines.extend(f"- `{pair_id}`" for pair_id in report["real_model_pair_ids"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Expansion Backlog",
            "",
            "| pair_id | base | target | recommended_models |",
            "| --- | --- | --- | --- |",
        ]
    )
    if report["expansion_backlog"]:
        lines.extend(
            f"| `{item['pair_id']}` | {item['base']} | {item['target']} | {', '.join(item['recommended_models'])} |"
            for item in report["expansion_backlog"]
        )
    else:
        lines.append("| n/a | n/a | n/a | n/a |")
    lines.extend(["", "## Recommended Next Actions", ""])
    lines.extend(f"- {item}" for item in report["recommended_next_actions"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
