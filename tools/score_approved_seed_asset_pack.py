from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from statistics import mean, pstdev
from typing import Any

from PIL import Image

from gitai_phase0.cli import build_judge, build_ocr
from gitai_phase0.domain import CaseSpec, DEFAULT_TEMPLATE_SET
from gitai_phase0.puzzle import CurationPolicy
from gitai_phase0.repositories import SeedScoreRef
from gitai_phase0.scoring import entropy, score_case

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_DIR = ROOT / "data" / "puzzle" / "approved_seed_asset_pack"
DEFAULT_OUT_DIR = ROOT / "reports" / "phase2" / "approved_seed_scores"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score approved SeedAsset fixtures and write SeedScores drafts."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_PACK_DIR / "approved_seed_cases.json")
    parser.add_argument("--images-root", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model", choices=("heuristic", "open_clip", "siglip"), default="heuristic")
    parser.add_argument("--ocr", choices=("known_text", "none", "tesseract"), default="known_text")
    parser.add_argument("--tau", type=float, default=30.0)
    parser.add_argument("--ref-date", default="")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--open-clip-model", default="ViT-L-14")
    parser.add_argument("--open-clip-pretrained", default="openai")
    parser.add_argument("--siglip-model-id", default="google/siglip-base-patch16-224")
    args = parser.parse_args()

    images_root = args.images_root or args.cases.parent
    payload = score_seed_asset_pack(
        cases_path=args.cases,
        images_root=images_root,
        out_dir=args.out_dir,
        model=args.model,
        ocr=args.ocr,
        tau=args.tau,
        ref_date=args.ref_date or datetime.now(timezone.utc).date().isoformat(),
        device=args.device,
        open_clip_model=args.open_clip_model,
        open_clip_pretrained=args.open_clip_pretrained,
        siglip_model_id=args.siglip_model_id,
    )
    print(f"Wrote {args.out_dir / 'approved_seed_scores.json'}")
    print(f"Wrote {args.out_dir / 'approved_measured_quality.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_score_results.json'}")
    print(f"Wrote {args.out_dir / 'approved_seed_score_report.md'}")
    print(f"Wrote {len(payload['seed_scores'])} SeedScores draft refs")


def score_seed_asset_pack(
    cases_path: Path,
    images_root: Path,
    out_dir: Path,
    model: str = "heuristic",
    ocr: str = "known_text",
    tau: float = 30.0,
    ref_date: str = "",
    device: str = "cpu",
    open_clip_model: str = "ViT-L-14",
    open_clip_pretrained: str = "openai",
    siglip_model_id: str = "google/siglip-base-patch16-224",
) -> dict[str, Any]:
    args = argparse.Namespace(
        model=model,
        device=device,
        open_clip_model=open_clip_model,
        open_clip_pretrained=open_clip_pretrained,
        siglip_model_id=siglip_model_id,
    )
    judge = build_judge(args)
    scanner = build_ocr(ocr)
    cases = load_cases(cases_path)
    results = [
        score_case(
            image=Image.open(images_root / case.image_path).convert("RGBA"),
            case=case,
            judge=judge,
            ocr=scanner,
            tau=tau,
        )
        for case in cases
    ]
    seed_scores = build_seed_scores(
        cases=cases,
        results=results,
        model_version=judge.model_version,
        tau=tau,
        ref_date=ref_date or datetime.now(timezone.utc).date().isoformat(),
    )
    policy = CurationPolicy()
    qualities = [quality_to_dict(policy.evaluate_seed_scores(SeedScoreRef.from_dict(item))) for item in seed_scores]
    payload = {
        "seed_scores": seed_scores,
        "qualities": qualities,
        "results": score_results_to_dict(cases, results),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "approved_seed_scores.json", {"seed_scores": seed_scores})
    write_json(out_dir / "approved_measured_quality.json", {"qualities": qualities})
    write_json(out_dir / "approved_seed_score_results.json", {"results": payload["results"]})
    (out_dir / "approved_seed_score_report.md").write_text(
        render_markdown(payload, model_version=judge.model_version, tau=tau),
        encoding="utf-8",
    )
    return payload


def load_cases(path: Path) -> list[CaseSpec]:
    return [CaseSpec.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8"))["cases"]]


def build_seed_scores(
    cases: list[CaseSpec],
    results,
    model_version: str,
    tau: float,
    ref_date: str,
) -> list[dict[str, Any]]:
    case_by_id = {case.case_id: case for case in cases}
    raw_by_pair: dict[str, list[float]] = {}
    for result in results:
        case = case_by_id[result.case_id]
        if case.expected_quality == "attack":
            continue
        raw_by_pair.setdefault(case.pair.pair_id, []).append(result.raw)
    refs: list[dict[str, Any]] = []
    for pair_id, scores in sorted(raw_by_pair.items()):
        sorted_scores = sorted(scores)
        refs.append(
            {
                "ref_version": seed_ref_version(
                    pair_id=pair_id,
                    model_version=model_version,
                    tau=tau,
                    ref_date=ref_date,
                ),
                "pair_id": pair_id,
                "model_version": model_version,
                "template_set_id": DEFAULT_TEMPLATE_SET.template_set_id,
                "tau": tau,
                "scores_sorted": sorted_scores,
                "stats": stats(sorted_scores),
            }
        )
    return refs


def seed_ref_version(pair_id: str, model_version: str, tau: float, ref_date: str) -> str:
    return (
        f"approved-seed-{slug(model_version)}-{pair_id.replace('_to_', '-')}"
        f"-tau{tau_slug(tau)}-{ref_date}"
    )


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def tau_slug(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value).replace(".", "p")


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


def quality_to_dict(quality) -> dict[str, Any]:
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


def score_results_to_dict(cases: list[CaseSpec], results) -> list[dict[str, Any]]:
    case_by_id = {case.case_id: case for case in cases}
    rows = []
    for result in results:
        case = case_by_id[result.case_id]
        rows.append(
            {
                "case_id": result.case_id,
                "pair_id": case.pair.pair_id,
                "image_path": case.image_path,
                "expected_quality": case.expected_quality,
                "expected_rank": case.expected_rank,
                "entropy": entropy(result.probabilities),
                **asdict(result),
            }
        )
    return rows


def render_markdown(payload: dict[str, Any], model_version: str, tau: float) -> str:
    lines = [
        "# Approved SeedScores draft",
        "",
        f"- model_version: `{model_version}`",
        f"- template_set_id: `{DEFAULT_TEMPLATE_SET.template_set_id}`",
        f"- tau: `{tau:g}`",
        f"- seed_score_refs: `{len(payload['seed_scores'])}`",
        "",
        "## Measured Quality",
        "",
        "| ref_version | pair_id | accepted | spread | p10 | p50 | p90 | measured | reasons |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for quality in payload["qualities"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    quality["ref_version"],
                    quality["pair_id"],
                    str(quality["accepted"]).lower(),
                    f"{quality['spread']:.4f}",
                    f"{quality['p10']:.4f}",
                    f"{quality['p50']:.4f}",
                    f"{quality['p90']:.4f}",
                    quality["measured_difficulty"],
                    ", ".join(quality["rejection_reasons"]) or "-",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Case Scores",
            "",
            "| pair_id | case_id | expected | raw | Cy | Cx | bucket |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for result in sorted(payload["results"], key=lambda item: (item["pair_id"], item["expected_rank"])):
        lines.append(
            "| "
            + " | ".join(
                [
                    result["pair_id"],
                    result["case_id"],
                    result["expected_quality"],
                    f"{result['raw']:.4f}",
                    f"{result['confidences']['Cy']:.4f}",
                    f"{result['confidences']['Cx']:.4f}",
                    result["bucket"],
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
