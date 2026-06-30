from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from gitai_phase0.domain import CaseSpec, ObjectLabel, PairSpec
from gitai_phase0.heuristic_judge import HeuristicJudge
from gitai_phase0.ocr import KnownTextOcrScanner
from gitai_phase0.reporting import load_cases
from gitai_phase0.scoring import percentile_rank, score_case


def test_percentile_rank_is_deterministic_left_bisect() -> None:
    scores = [0.1, 0.2, 0.2, 0.4]
    assert percentile_rank(0.2, scores) == 0.25
    assert percentile_rank(0.3, scores) == 0.75


def test_ocr_attack_hard_zeroes_raw() -> None:
    image = blank_circle()
    case = CaseSpec(
        case_id="attack",
        image_path="attack.png",
        pair=PairSpec(
            pair_id="apple_to_baseball",
            base=ObjectLabel("apple", "apple"),
            target=ObjectLabel("baseball", "baseball", ("base ball",)),
            hard_negatives=(ObjectLabel("tennis_ball", "tennis ball"),),
        ),
        expected_quality="attack",
        expected_rank=0,
        known_text=("BASEBALL",),
    )
    result = score_case(image, case, HeuristicJudge(), KnownTextOcrScanner(), tau=30.0)
    assert result.ocr_cheat is True
    assert result.raw == 0.0
    assert result.bucket == "failed"


def test_scoring_is_repeatable() -> None:
    image = blank_circle()
    case = CaseSpec(
        case_id="repeat",
        image_path="repeat.png",
        pair=PairSpec(
            pair_id="apple_to_baseball",
            base=ObjectLabel("apple", "apple"),
            target=ObjectLabel("baseball", "baseball"),
            hard_negatives=(ObjectLabel("tennis_ball", "tennis ball"),),
        ),
        expected_quality="strong",
        expected_rank=0,
    )
    judge = HeuristicJudge()
    ocr = KnownTextOcrScanner()
    first = score_case(image, case, judge, ocr, tau=30.0)
    second = score_case(image, case, judge, ocr, tau=30.0)
    assert first == second


def test_generated_dataset_orders_good_above_plain() -> None:
    dataset = Path("data/phase0/cases.json")
    if not dataset.exists():
        pytest.skip("Run tools/make_phase0_samples.py first.")
    cases = load_cases(dataset)
    images_root = Path("data/phase0/images")
    judge = HeuristicJudge()
    ocr = KnownTextOcrScanner()
    by_id = {}
    for case in cases:
        image = Image.open(images_root / case.image_path)
        by_id[case.case_id] = score_case(image, case, judge, ocr, tau=30.0)
    assert by_id["apple_baseball_good"].raw > by_id["apple_plain"].raw
    assert by_id["apple_baseball_text_attack"].raw == 0.0


def blank_circle() -> Image.Image:
    image = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((32, 32, 224, 224), fill=(245, 245, 238, 255))
    draw.arc((45, 40, 115, 225), start=290, end=70, fill=(206, 35, 44, 255), width=6)
    draw.arc((140, 40, 210, 225), start=110, end=250, fill=(206, 35, 44, 255), width=6)
    return image
