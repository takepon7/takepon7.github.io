from __future__ import annotations

import argparse
from pathlib import Path

from gitai_phase0.heuristic_judge import HeuristicJudge
from gitai_phase0.ocr import KnownTextOcrScanner, NullOcrScanner, TesseractOcrScanner
from gitai_phase0.open_clip_judge import OpenClipJudge
from gitai_phase0.reporting import load_cases, run_sweep, write_outputs
from gitai_phase0.siglip_judge import SiglipJudge


def main() -> None:
    parser = argparse.ArgumentParser(description="Run gitai Phase 0 scoring harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--cases", type=Path, default=Path("data/phase0/cases.json"))
    run_parser.add_argument("--images-root", type=Path, default=Path("data/phase0/images"))
    run_parser.add_argument("--out-dir", type=Path, default=Path("reports/phase0"))
    run_parser.add_argument("--model", choices=("heuristic", "open_clip", "siglip"), default="heuristic")
    run_parser.add_argument("--ocr", choices=("known_text", "none", "tesseract"), default="known_text")
    run_parser.add_argument("--taus", type=float, nargs="+", default=[100.0, 50.0, 30.0, 20.0])
    run_parser.add_argument("--device", default="cpu")
    run_parser.add_argument("--open-clip-model", default="ViT-L-14")
    run_parser.add_argument("--open-clip-pretrained", default="openai")
    run_parser.add_argument("--siglip-model-id", default="google/siglip-base-patch16-224")

    args = parser.parse_args()
    if args.command == "run":
        judge = build_judge(args)
        ocr = build_ocr(args.ocr)
        cases = load_cases(args.cases)
        results = run_sweep(
            cases=cases,
            images_root=args.images_root,
            judge=judge,
            ocr=ocr,
            taus=tuple(args.taus),
        )
        write_outputs(out_dir=args.out_dir, cases=cases, results=results, judge=judge)
        print(f"Wrote Phase 0 report to {args.out_dir}")


def build_judge(args: argparse.Namespace):
    if args.model == "heuristic":
        return HeuristicJudge()
    if args.model == "open_clip":
        return OpenClipJudge(
            model_name=args.open_clip_model,
            pretrained=args.open_clip_pretrained,
            device=args.device,
        )
    if args.model == "siglip":
        return SiglipJudge(model_id=args.siglip_model_id, device=args.device)
    raise ValueError(args.model)


def build_ocr(kind: str):
    if kind == "known_text":
        return KnownTextOcrScanner()
    if kind == "none":
        return NullOcrScanner()
    if kind == "tesseract":
        return TesseractOcrScanner()
    raise ValueError(kind)


if __name__ == "__main__":
    main()
