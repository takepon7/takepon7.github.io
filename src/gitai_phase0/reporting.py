from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean

from PIL import Image, ImageDraw

from gitai_phase0.domain import CaseSpec, DEFAULT_TEMPLATE_SET, ScoreResult
from gitai_phase0.ports import JudgeModel, OcrScanner
from gitai_phase0.scoring import entropy, score_case


def load_cases(path: Path) -> list[CaseSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [CaseSpec.from_dict(item) for item in data["cases"]]


def run_sweep(
    cases: list[CaseSpec],
    images_root: Path,
    judge: JudgeModel,
    ocr: OcrScanner,
    taus: tuple[float, ...],
) -> list[ScoreResult]:
    results: list[ScoreResult] = []
    for tau in taus:
        for case in cases:
            image = Image.open(images_root / case.image_path)
            results.append(score_case(image=image, case=case, judge=judge, ocr=ocr, tau=tau))
    return results


def write_outputs(
    out_dir: Path,
    cases: list[CaseSpec],
    results: list[ScoreResult],
    judge: JudgeModel,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "results.json", cases, results)
    write_csv(out_dir / "results.csv", cases, results)
    write_report(out_dir / "report.md", cases, results, judge)
    write_chart(out_dir / "tau_sweep.png", cases, results)


def write_json(path: Path, cases: list[CaseSpec], results: list[ScoreResult]) -> None:
    case_by_id = {case.case_id: case for case in cases}
    payload = []
    for result in results:
        case = case_by_id[result.case_id]
        payload.append(
            {
                "case_id": result.case_id,
                "image_path": case.image_path,
                "expected_quality": case.expected_quality,
                "expected_rank": case.expected_rank,
                **asdict(result),
            }
        )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(path: Path, cases: list[CaseSpec], results: list[ScoreResult]) -> None:
    case_by_id = {case.case_id: case for case in cases}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "tau",
                "case_id",
                "expected_quality",
                "expected_rank",
                "raw",
                "Cy",
                "Cx",
                "bucket",
                "ocr_cheat",
                "entropy",
            ],
        )
        writer.writeheader()
        for result in results:
            case = case_by_id[result.case_id]
            writer.writerow(
                {
                    "tau": result.tau,
                    "case_id": result.case_id,
                    "expected_quality": case.expected_quality,
                    "expected_rank": case.expected_rank,
                    "raw": f"{result.raw:.8f}",
                    "Cy": f"{result.confidences.Cy:.8f}",
                    "Cx": f"{result.confidences.Cx:.8f}",
                    "bucket": result.bucket,
                    "ocr_cheat": result.ocr_cheat,
                    "entropy": f"{entropy(result.probabilities):.8f}",
                }
            )


def write_report(
    path: Path,
    cases: list[CaseSpec],
    results: list[ScoreResult],
    judge: JudgeModel,
) -> None:
    lines: list[str] = []
    lines.append("# Phase 0 scoring harness report")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- model_version: `{judge.model_version}`")
    lines.append(f"- template_set_id: `{DEFAULT_TEMPLATE_SET.template_set_id}`")
    lines.append("- raw formula: `Cy * (1 - Cx)`, hard-zeroed on OCR attack")
    lines.append("")
    if judge.model_version.startswith("heuristic"):
        lines.append(
            "Note: this run uses the deterministic heuristic judge. It validates the "
            "harness, OCR guard, and tau sweep only. Real go/no-go still requires "
            "OpenCLIP/SigLIP model runs."
        )
        lines.append("")

    for tau in sorted({result.tau for result in results}, reverse=True):
        tau_results = [result for result in results if result.tau == tau]
        lines.append(f"## Tau {tau:g}")
        lines.append("")
        lines.append("| case | expected | raw | Cy | Cx | bucket | ocr | entropy |")
        lines.append("| --- | --- | ---: | ---: | ---: | --- | --- | ---: |")
        for result in sorted(tau_results, key=lambda item: case_rank(cases, item.case_id)):
            case = find_case(cases, result.case_id)
            lines.append(
                "| "
                + " | ".join(
                    [
                        result.case_id,
                        case.expected_quality,
                        f"{result.raw:.4f}",
                        f"{result.confidences.Cy:.4f}",
                        f"{result.confidences.Cx:.4f}",
                        result.bucket,
                        str(result.ocr_cheat).lower(),
                        f"{entropy(result.probabilities):.4f}",
                    ]
                )
                + " |"
            )
        spread = max(item.raw for item in tau_results) - min(item.raw for item in tau_results)
        smoothness = mean(entropy(item.probabilities) for item in tau_results)
        lines.append("")
        lines.append(f"- raw spread: `{spread:.4f}`")
        lines.append(f"- mean entropy: `{smoothness:.4f}`")
        lines.append("")

    lines.extend(question_answers(cases, results, judge))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def question_answers(
    cases: list[CaseSpec],
    results: list[ScoreResult],
    judge: JudgeModel,
) -> list[str]:
    lines = ["## Phase 0 questions", ""]
    non_attack = [case for case in cases if case.expected_quality != "attack"]
    by_tau = sorted({result.tau for result in results}, reverse=True)
    best_tau = 30.0 if 30.0 in by_tau else by_tau[-1]
    best_results = [result for result in results if result.tau == best_tau]
    strong = [
        result.raw
        for result in best_results
        if find_case(cases, result.case_id).expected_quality == "strong"
    ]
    weak = [
        result.raw
        for result in best_results
        if find_case(cases, result.case_id).expected_quality == "weak"
    ]
    attacks = [
        result
        for result in best_results
        if find_case(cases, result.case_id).expected_quality == "attack"
    ]
    if strong and weak:
        delta = mean(strong) - mean(weak)
        lines.append(f"- Q1 spread check at tau {best_tau:g}: strong-minus-weak raw delta = `{delta:.4f}`.")
    else:
        lines.append("- Q1 spread check: not enough weak/strong cases in this dataset.")
    if attacks:
        zeroed = all(result.ocr_cheat and result.raw == 0.0 for result in attacks)
        lines.append(f"- Q2 text attack check: OCR hard-zero passed = `{str(zeroed).lower()}`.")
    else:
        lines.append("- Q2 text attack check: no attack case in this dataset.")
    entropies = [
        (
            tau,
            mean(entropy(result.probabilities) for result in results if result.tau == tau),
        )
        for tau in by_tau
    ]
    lines.append(
        "- Q3 tau smoothness check: mean entropy by tau = "
        + ", ".join(f"{tau:g}:{value:.4f}" for tau, value in entropies)
        + "."
    )
    if judge.model_version.startswith("heuristic"):
        lines.append(
            "- Gate: `not decided`. The offline heuristic run cannot prove the game; "
            "it only proves the harness is ready for real model scoring."
        )
    else:
        passed = bool(strong and weak and mean(strong) > mean(weak))
        attack_passed = all(result.ocr_cheat and result.raw == 0.0 for result in attacks)
        lines.append(f"- Gate: `{'go' if passed and attack_passed else 'no-go'}` for this dataset/model run.")
    lines.append("")
    lines.append(f"- non_attack_cases: `{len(non_attack)}`")
    return lines


def write_chart(path: Path, cases: list[CaseSpec], results: list[ScoreResult]) -> None:
    width = 980
    row_height = 28
    taus = sorted({result.tau for result in results}, reverse=True)
    height = 80 + row_height * len(cases) * len(taus)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 20), "Phase 0 tau sweep raw scores", fill=(20, 20, 20))
    y = 58
    for tau in taus:
        draw.text((24, y), f"tau {tau:g}", fill=(20, 20, 20))
        y += row_height
        tau_results = [result for result in results if result.tau == tau]
        max_raw = max((result.raw for result in tau_results), default=1.0) or 1.0
        for result in sorted(tau_results, key=lambda item: case_rank(cases, item.case_id)):
            case = find_case(cases, result.case_id)
            bar_width = int(520 * (result.raw / max_raw))
            color = (42, 111, 201)
            if case.expected_quality == "attack":
                color = (180, 54, 54)
            elif case.expected_quality == "strong":
                color = (44, 145, 92)
            draw.text((54, y + 5), f"{result.case_id} ({case.expected_quality})", fill=(40, 40, 40))
            draw.rectangle((320, y + 5, 320 + bar_width, y + 22), fill=color)
            draw.text((850, y + 5), f"{result.raw:.4f}", fill=(40, 40, 40))
            y += row_height
        y += 8
    image.save(path)


def find_case(cases: list[CaseSpec], case_id: str) -> CaseSpec:
    for case in cases:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def case_rank(cases: list[CaseSpec], case_id: str) -> int:
    return find_case(cases, case_id).expected_rank
