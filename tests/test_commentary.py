from __future__ import annotations

from pathlib import Path

from gitai_phase0.commentary import (
    build_appraisal_comment,
    build_layer2_prompt,
    parse_layer2_appraisal_response,
)
from gitai_phase0.competition import PlayerIdentity, SubmissionRecord
from gitai_phase0.repositories import PairRepository
from datetime import date, datetime, timezone


def test_template_bank_comment_is_deterministic() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")

    first = build_appraisal_comment(
        pair=pair,
        bucket="fooled",
        score=1000,
        cy=0.91,
        cx=0.02,
        ocr_cheat=False,
        moderation="pass",
        selector="same-submission",
    )
    second = build_appraisal_comment(
        pair=pair,
        bucket="fooled",
        score=1000,
        cy=0.91,
        cx=0.02,
        ocr_cheat=False,
        moderation="pass",
        selector="same-submission",
    )

    assert first == second
    assert first.source == "template_bank"
    assert first.mood in {"smug", "delighted", "suspicious", "exasperated"}
    assert "baseball" in first.line


def test_template_bank_uses_safe_fallbacks() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")

    cheat = build_appraisal_comment(
        pair=pair,
        bucket="fooled",
        score=0,
        cy=1.0,
        cx=0.0,
        ocr_cheat=True,
        moderation="pass",
        selector="text-cheat",
    )
    flagged = build_appraisal_comment(
        pair=pair,
        bucket="fooled",
        score=1000,
        cy=1.0,
        cx=0.0,
        ocr_cheat=False,
        moderation="flag",
        selector="flagged",
    )

    assert cheat.line == "文字ではなく、絵で化けましょう。"
    assert flagged.template_id == "ja-moderation-001"


def test_layer2_prompt_keeps_verdict_authority_fixed() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")
    prompt = build_layer2_prompt(submission_record(), pair)

    assert "覆したり再判定してはいけません" in prompt.system
    assert "描いた人間" in prompt.system
    assert '"target": "baseball"' in prompt.user
    assert '"bucket": "fooled"' in prompt.user


def test_layer2_response_parser_rejects_person_attacks() -> None:
    safe = parse_layer2_appraisal_response('{"line":"これは見事なbaseballです。","mood":"smug"}')
    unsafe = parse_layer2_appraisal_response('{"line":"あなたはバカです。","mood":"smug"}')
    malformed = parse_layer2_appraisal_response("これはbaseballです")

    assert safe is not None
    assert safe.source == "layer2"
    assert unsafe is None
    assert malformed is None


def submission_record() -> SubmissionRecord:
    return SubmissionRecord(
        submission_id="commentary-test",
        puzzle_date=date(2026, 6, 29),
        pair_id="apple_to_baseball",
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity(user_id="artist", display_name="artist"),
        image_hash="commentary-test",
        image_ref="memory:commentary-test",
        stroke_count=1,
        score=1000,
        percentile=1.0,
        raw=1.0,
        bucket="fooled",
        ocr_cheat=False,
        moderation="pass",
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )
