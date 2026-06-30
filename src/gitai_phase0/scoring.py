from __future__ import annotations

from bisect import bisect_left
from difflib import SequenceMatcher
import math
import re

import numpy as np
from PIL import Image

from gitai_phase0.domain import (
    DEFAULT_TEMPLATE_SET,
    CaseSpec,
    Confidence,
    ScoreBucket,
    ScoreResult,
    TemplateSet,
)
from gitai_phase0.ports import JudgeModel, OcrScanner

TEXT_ATTACK_THRESHOLD = 0.86


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        raise ValueError("Cannot normalize a zero vector.")
    return arr / norm


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(normalize_vector(left), normalize_vector(right)))


def softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    max_logit = max(logits)
    exps = [math.exp(item - max_logit) for item in logits]
    total = sum(exps)
    return [item / total for item in exps]


def percentile_rank(raw: float, scores_sorted: list[float] | tuple[float, ...]) -> float:
    if not scores_sorted:
        raise ValueError("scores_sorted must not be empty.")
    return bisect_left(scores_sorted, raw) / len(scores_sorted)


def score_case(
    image: Image.Image,
    case: CaseSpec,
    judge: JudgeModel,
    ocr: OcrScanner,
    tau: float,
    template_set: TemplateSet = DEFAULT_TEMPLATE_SET,
    text_threshold: float = TEXT_ATTACK_THRESHOLD,
) -> ScoreResult:
    detected_text = ocr.scan(image, case)
    ocr_cheat = is_typographic_attack(
        detected_text=detected_text,
        guard_terms=case.pair.ocr_guard_terms,
        threshold=text_threshold,
    )

    image_vector = judge.encode_image(image)
    candidate_vectors = [
        judge.encode_text(label, template_set) for label in case.pair.candidate_labels
    ]
    logits = [cosine(image_vector, candidate) * tau for candidate in candidate_vectors]
    probabilities = tuple(softmax(logits))
    cy = probabilities[0]
    cx = probabilities[1]
    negs = probabilities[2:]
    raw = cy * (1.0 - cx)
    if ocr_cheat:
        raw = 0.0

    return ScoreResult(
        case_id=case.case_id,
        tau=tau,
        raw=raw,
        confidences=Confidence(Cy=cy, Cx=cx, negs=tuple(negs)),
        bucket=bucket_for(cy=cy, cx=cx, ocr_cheat=ocr_cheat),
        ocr_cheat=ocr_cheat,
        detected_text=detected_text,
        probabilities=probabilities,
        candidate_labels=case.pair.candidate_labels,
        model_version=judge.model_version,
        template_set_id=template_set.template_set_id,
    )


def bucket_for(cy: float, cx: float, ocr_cheat: bool) -> ScoreBucket:
    if ocr_cheat:
        return "failed"
    if cy >= 0.55 and cy > cx:
        return "fooled"
    if abs(cy - cx) <= 0.15:
        return "confused"
    return "failed"


def is_typographic_attack(
    detected_text: tuple[str, ...],
    guard_terms: tuple[str, ...],
    threshold: float,
) -> bool:
    for text in detected_text:
        normalized_text = normalize_text(text)
        if not normalized_text:
            continue
        for guard in guard_terms:
            normalized_guard = normalize_text(guard)
            if not normalized_guard:
                continue
            if normalized_guard in normalized_text:
                return True
            if SequenceMatcher(None, normalized_text, normalized_guard).ratio() >= threshold:
                return True
    return False


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def entropy(probabilities: tuple[float, ...]) -> float:
    return -sum(item * math.log(item) for item in probabilities if item > 0.0)
