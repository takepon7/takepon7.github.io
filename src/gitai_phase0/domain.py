from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ScoreBucket = Literal["fooled", "failed", "confused"]
ExpectedQuality = Literal["weak", "medium", "strong", "attack"]


@dataclass(frozen=True)
class ObjectLabel:
    object_id: str
    canonical_label: str
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObjectLabel":
        return cls(
            object_id=str(data["object_id"]),
            canonical_label=str(data["canonical_label"]),
            aliases=tuple(str(item) for item in data.get("aliases", ())),
        )

    @property
    def guard_terms(self) -> tuple[str, ...]:
        return (self.canonical_label, *self.aliases)


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    base: ObjectLabel
    target: ObjectLabel
    hard_negatives: tuple[ObjectLabel, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PairSpec":
        return cls(
            pair_id=str(data["pair_id"]),
            base=ObjectLabel.from_dict(data["base"]),
            target=ObjectLabel.from_dict(data["target"]),
            hard_negatives=tuple(
                ObjectLabel.from_dict(item) for item in data.get("hard_negatives", ())
            ),
        )

    @property
    def candidate_labels(self) -> tuple[str, ...]:
        return (
            self.target.canonical_label,
            self.base.canonical_label,
            *(item.canonical_label for item in self.hard_negatives),
        )

    @property
    def ocr_guard_terms(self) -> tuple[str, ...]:
        terms: list[str] = []
        terms.extend(self.target.guard_terms)
        for negative in self.hard_negatives:
            terms.extend(negative.guard_terms)
        return tuple(terms)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    image_path: str
    pair: PairSpec
    expected_quality: ExpectedQuality
    expected_rank: int
    known_text: tuple[str, ...] = ()
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseSpec":
        return cls(
            case_id=str(data["case_id"]),
            image_path=str(data["image_path"]),
            pair=PairSpec.from_dict(data["pair"]),
            expected_quality=data["expected_quality"],
            expected_rank=int(data["expected_rank"]),
            known_text=tuple(str(item) for item in data.get("known_text", ())),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class TemplateSet:
    template_set_id: str
    templates: tuple[str, ...]


DEFAULT_TEMPLATE_SET = TemplateSet(
    template_set_id="drawing_v1",
    templates=(
        "a crude drawing of {label}",
        "a child's sketch of {label}",
        "a simple drawing of {label}",
    ),
)


@dataclass(frozen=True)
class Confidence:
    Cy: float
    Cx: float
    negs: tuple[float, ...]


@dataclass(frozen=True)
class ScoreResult:
    case_id: str
    tau: float
    raw: float
    confidences: Confidence
    bucket: ScoreBucket
    ocr_cheat: bool
    detected_text: tuple[str, ...]
    probabilities: tuple[float, ...]
    candidate_labels: tuple[str, ...]
    model_version: str
    template_set_id: str
