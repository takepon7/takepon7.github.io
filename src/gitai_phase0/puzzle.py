from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
import hashlib
import math
from typing import Any, Literal

from gitai_phase0.domain import ObjectLabel, PairSpec

ObjectStatus = Literal["active", "retired"]
ObjectSource = Literal["llm_proposed", "human_curated"]
PairStatus = Literal["candidate", "seeded", "active", "retired"]
PairProposalStatus = Literal["candidate", "needs_catalog_review", "approved", "rejected"]
PairProposalReviewDecision = Literal["approved", "needs_catalog_review", "rejected"]
SeedAssetQuality = Literal["weak", "medium", "strong"]


@dataclass(frozen=True)
class ShapeVector:
    roundness: float
    slenderness: float
    flatness: float
    limbness: float
    detail_density: float

    def __post_init__(self) -> None:
        for value in self.values:
            if value < 0.0 or value > 1.0:
                raise ValueError("ShapeVector values must be in [0, 1].")

    @classmethod
    def from_iterable(cls, values: list[float] | tuple[float, ...]) -> "ShapeVector":
        if len(values) != 5:
            raise ValueError("shape_vec must have exactly 5 values.")
        return cls(*(float(value) for value in values))

    @property
    def values(self) -> tuple[float, float, float, float, float]:
        return (
            self.roundness,
            self.slenderness,
            self.flatness,
            self.limbness,
            self.detail_density,
        )

    def distance_to(self, other: "ShapeVector") -> float:
        total = sum((left - right) ** 2 for left, right in zip(self.values, other.values))
        return math.sqrt(total) / math.sqrt(5)


@dataclass(frozen=True)
class CatalogObject:
    object_id: str
    canonical_label: str
    aliases: tuple[str, ...]
    shape_vec: ShapeVector
    malleability: float
    evocability: float
    category: str
    dominant_colors: tuple[str, ...]
    status: ObjectStatus
    source: ObjectSource

    def __post_init__(self) -> None:
        for name, value in (
            ("malleability", self.malleability),
            ("evocability", self.evocability),
        ):
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be in [0, 1].")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogObject":
        return cls(
            object_id=str(data["object_id"]),
            canonical_label=str(data["canonical_label"]),
            aliases=tuple(str(item) for item in data.get("aliases", ())),
            shape_vec=ShapeVector.from_iterable(tuple(float(item) for item in data["shape_vec"])),
            malleability=float(data["malleability"]),
            evocability=float(data["evocability"]),
            category=str(data["category"]),
            dominant_colors=tuple(str(item) for item in data.get("dominant_colors", ())),
            status=data.get("status", "active"),
            source=data.get("source", "human_curated"),
        )

    def to_object_label(self) -> ObjectLabel:
        return ObjectLabel(
            object_id=self.object_id,
            canonical_label=self.canonical_label,
            aliases=self.aliases,
        )


@dataclass(frozen=True)
class CandidatePair:
    pair_id: str
    base: CatalogObject
    target: CatalogObject
    hard_negatives: tuple[CatalogObject, ...]
    difficulty_prior: float
    status: PairStatus = "candidate"

    def to_pair_spec(self) -> PairSpec:
        return PairSpec(
            pair_id=self.pair_id,
            base=self.base.to_object_label(),
            target=self.target.to_object_label(),
            hard_negatives=tuple(item.to_object_label() for item in self.hard_negatives),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "base": object_ref(self.base),
            "target": object_ref(self.target),
            "hard_negatives": [object_ref(item) for item in self.hard_negatives],
            "difficulty_prior": self.difficulty_prior,
            "status": self.status,
        }


@dataclass(frozen=True)
class ApprovedPairSeedQueueEntry:
    proposal_id: str
    pair_key: str
    pair_id: str
    base: CatalogObject
    target: CatalogObject
    hard_negatives: tuple[CatalogObject, ...]
    difficulty_prior: float
    support_count: int
    reviewer_id: str
    review_note: str
    reviewed_at: datetime | None
    status: str = "ready_for_seed_generation"

    def to_candidate_pair(self) -> CandidatePair:
        return CandidatePair(
            pair_id=self.pair_id,
            base=self.base,
            target=self.target,
            hard_negatives=self.hard_negatives,
            difficulty_prior=self.difficulty_prior,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "pair_key": self.pair_key,
            "pair_id": self.pair_id,
            "base": object_ref(self.base),
            "target": object_ref(self.target),
            "hard_negatives": [object_ref(item) for item in self.hard_negatives],
            "difficulty_prior": self.difficulty_prior,
            "support_count": self.support_count,
            "reviewer_id": self.reviewer_id,
            "review_note": self.review_note,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "status": self.status,
        }


@dataclass(frozen=True)
class SeedAsset:
    asset_id: str
    proposal_id: str
    pair_id: str
    variant: SeedAssetQuality
    image_ref: str
    gen_model: str
    gen_prompt: str
    gen_params_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise ValueError("asset_id must not be blank.")
        if not self.pair_id:
            raise ValueError("pair_id must not be blank.")
        if not self.image_ref:
            raise ValueError("image_ref must not be blank.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "proposal_id": self.proposal_id,
            "pair_id": self.pair_id,
            "variant": self.variant,
            "image_ref": self.image_ref,
            "gen_model": self.gen_model,
            "gen_prompt": self.gen_prompt,
            "gen_params_hash": self.gen_params_hash,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class PuzzleQuality:
    ref_version: str
    pair_id: str
    spread: float
    p10: float
    p50: float
    p90: float
    accepted: bool
    measured_difficulty: str
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DailyPuzzle:
    date: date
    pair_id: str
    ref_version: str
    frozen_at: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "date": self.date.isoformat(),
            "pair_id": self.pair_id,
            "ref_version": self.ref_version,
            "frozen_at": self.frozen_at.isoformat(),
        }


@dataclass(frozen=True)
class PairProposalEvaluation:
    status: PairProposalStatus
    rejection_reasons: tuple[str, ...]
    difficulty_prior: float | None
    base: CatalogObject | None
    target: CatalogObject | None
    hard_negatives: tuple[CatalogObject, ...] = ()


@dataclass(frozen=True)
class PairProposal:
    proposal_id: str
    pair_key: str
    user_id: str
    base_label: str
    target_label: str
    base_object_id: str
    target_object_id: str
    status: PairProposalStatus
    rejection_reasons: tuple[str, ...]
    difficulty_prior: float | None
    hard_negative_ids: tuple[str, ...]
    support_count: int
    created_at: datetime
    last_supported_at: datetime
    reviewer_id: str = ""
    review_note: str = ""
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.support_count < 1:
            raise ValueError("support_count must be at least 1.")
        if self.status == "approved" and (
            not self.base_object_id or not self.target_object_id
        ):
            raise ValueError("approved pair proposals must have known catalog objects.")
        normalize_pair_proposal_review_note(self.review_note)

    def review(
        self,
        status: PairProposalReviewDecision,
        reviewer_id: str,
        note: str = "",
        reviewed_at: datetime | None = None,
    ) -> "PairProposal":
        if status == "approved" and (
            not self.base_object_id or not self.target_object_id
        ):
            raise ValueError("approved pair proposals must have known catalog objects.")
        rejection_reasons: tuple[str, ...]
        if status == "approved":
            rejection_reasons = ()
        elif status == "needs_catalog_review":
            rejection_reasons = self.rejection_reasons or ("operator_catalog_review",)
        else:
            rejection_reasons = self.rejection_reasons or ("operator_rejected",)
        return replace(
            self,
            status=status,
            rejection_reasons=rejection_reasons,
            reviewer_id=reviewer_id,
            review_note=normalize_pair_proposal_review_note(note),
            reviewed_at=reviewed_at or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "pair_key": self.pair_key,
            "user_id": self.user_id,
            "base_label": self.base_label,
            "target_label": self.target_label,
            "base_object_id": self.base_object_id,
            "target_object_id": self.target_object_id,
            "status": self.status,
            "rejection_reasons": list(self.rejection_reasons),
            "difficulty_prior": self.difficulty_prior,
            "hard_negative_ids": list(self.hard_negative_ids),
            "support_count": self.support_count,
            "created_at": self.created_at.isoformat(),
            "last_supported_at": self.last_supported_at.isoformat(),
            "reviewer_id": self.reviewer_id,
            "review_note": self.review_note,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class CurationPolicy:
    def __init__(
        self,
        spread_floor: float = 0.08,
        impossible_floor: float = 0.20,
        trivial_ceiling: float = 0.70,
        plausible_shape_distance: float = 0.80,
    ) -> None:
        self.spread_floor = spread_floor
        self.impossible_floor = impossible_floor
        self.trivial_ceiling = trivial_ceiling
        self.plausible_shape_distance = plausible_shape_distance

    def difficulty_prior(self, base: CatalogObject, target: CatalogObject) -> float:
        d_shape = base.shape_vec.distance_to(target.shape_vec)
        d_sem = lexical_semantic_distance(base.canonical_label, target.canonical_label)
        value = (
            0.55 * d_shape
            + 0.25 * (1.0 - base.malleability)
            + 0.15 * (1.0 - target.evocability)
            + 0.05 * d_sem
        )
        return clamp01(value)

    def is_plausible(self, base: CatalogObject, target: CatalogObject) -> bool:
        return base.shape_vec.distance_to(target.shape_vec) <= self.plausible_shape_distance

    def evaluate_pair_proposal(
        self,
        base_label: str,
        target_label: str,
        base: CatalogObject | None,
        target: CatalogObject | None,
        objects: list[CatalogObject],
        hard_negative_count: int = 3,
    ) -> PairProposalEvaluation:
        if base_label == target_label:
            return PairProposalEvaluation(
                status="rejected",
                rejection_reasons=("same_label",),
                difficulty_prior=None,
                base=base,
                target=target,
            )
        missing: list[str] = []
        if base is None:
            missing.append("unknown_base_label")
        if target is None:
            missing.append("unknown_target_label")
        if missing:
            return PairProposalEvaluation(
                status="needs_catalog_review",
                rejection_reasons=tuple(missing),
                difficulty_prior=None,
                base=base,
                target=target,
            )
        if base.object_id == target.object_id:
            return PairProposalEvaluation(
                status="rejected",
                rejection_reasons=("same_object",),
                difficulty_prior=None,
                base=base,
                target=target,
            )
        if base.status != "active" or target.status != "active":
            return PairProposalEvaluation(
                status="rejected",
                rejection_reasons=("inactive_object",),
                difficulty_prior=None,
                base=base,
                target=target,
            )
        difficulty_prior = self.difficulty_prior(base, target)
        hard_negatives = select_hard_negatives(
            base=base,
            target=target,
            objects=objects,
            count=hard_negative_count,
        )
        if not self.is_plausible(base, target):
            return PairProposalEvaluation(
                status="rejected",
                rejection_reasons=("shape_distance_above_plausible_gate",),
                difficulty_prior=difficulty_prior,
                base=base,
                target=target,
                hard_negatives=hard_negatives,
            )
        return PairProposalEvaluation(
            status="candidate",
            rejection_reasons=(),
            difficulty_prior=difficulty_prior,
            base=base,
            target=target,
            hard_negatives=hard_negatives,
        )

    def evaluate_seed_scores(self, ref) -> PuzzleQuality:
        p10 = ref.stats["p10"]
        p50 = ref.stats["p50"]
        p90 = ref.stats["p90"]
        spread = p90 - p10
        reasons: list[str] = []
        if spread < self.spread_floor:
            reasons.append("spread_below_floor")
        if p90 < self.impossible_floor:
            reasons.append("p90_below_impossible_floor")
        if p10 > self.trivial_ceiling:
            reasons.append("p10_above_trivial_ceiling")
        return PuzzleQuality(
            ref_version=ref.ref_version,
            pair_id=ref.pair_id,
            spread=spread,
            p10=p10,
            p50=p50,
            p90=p90,
            accepted=not reasons,
            measured_difficulty=measured_difficulty_bucket(p50),
            rejection_reasons=tuple(reasons),
        )


def generate_candidate_pairs(
    objects: list[CatalogObject],
    policy: CurationPolicy,
    hard_negative_count: int = 3,
) -> list[CandidatePair]:
    active = [item for item in objects if item.status == "active"]
    pairs: list[CandidatePair] = []
    for base in active:
        for target in active:
            if base.object_id == target.object_id:
                continue
            if not policy.is_plausible(base, target):
                continue
            pairs.append(
                CandidatePair(
                    pair_id=f"{base.object_id}_to_{target.object_id}",
                    base=base,
                    target=target,
                    hard_negatives=select_hard_negatives(
                        base=base,
                        target=target,
                        objects=active,
                        count=hard_negative_count,
                    ),
                    difficulty_prior=policy.difficulty_prior(base, target),
                )
            )
    return sorted(pairs, key=lambda item: (item.difficulty_prior, item.pair_id))


def select_hard_negatives(
    base: CatalogObject,
    target: CatalogObject,
    objects: list[CatalogObject],
    count: int,
) -> tuple[CatalogObject, ...]:
    candidates = [
        item
        for item in objects
        if item.object_id not in {base.object_id, target.object_id} and item.status == "active"
    ]
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.shape_vec.distance_to(base.shape_vec) + item.shape_vec.distance_to(target.shape_vec),
            item.object_id,
        ),
    )
    return tuple(ranked[:count])


def seed_queue_entry_from_approved_proposal(
    proposal: PairProposal,
    objects: list[CatalogObject],
    policy: CurationPolicy,
    hard_negative_count: int = 3,
) -> ApprovedPairSeedQueueEntry:
    if proposal.status != "approved":
        raise ValueError("pair proposal must be approved before seed generation.")
    by_id = {item.object_id: item for item in objects}
    try:
        base = by_id[proposal.base_object_id]
        target = by_id[proposal.target_object_id]
    except KeyError as exc:
        raise ValueError("approved pair proposal references an unknown catalog object.") from exc
    if base.status != "active" or target.status != "active":
        raise ValueError("approved pair proposal references an inactive catalog object.")
    if base.object_id == target.object_id:
        raise ValueError("approved pair proposal must not use the same catalog object.")
    hard_negatives = resolve_approved_hard_negatives(
        proposal=proposal,
        base=base,
        target=target,
        objects=objects,
        count=hard_negative_count,
    )
    difficulty_prior = (
        proposal.difficulty_prior
        if proposal.difficulty_prior is not None
        else policy.difficulty_prior(base, target)
    )
    return ApprovedPairSeedQueueEntry(
        proposal_id=proposal.proposal_id,
        pair_key=proposal.pair_key,
        pair_id=f"{base.object_id}_to_{target.object_id}",
        base=base,
        target=target,
        hard_negatives=hard_negatives,
        difficulty_prior=difficulty_prior,
        support_count=proposal.support_count,
        reviewer_id=proposal.reviewer_id,
        review_note=proposal.review_note,
        reviewed_at=proposal.reviewed_at,
    )


def resolve_approved_hard_negatives(
    proposal: PairProposal,
    base: CatalogObject,
    target: CatalogObject,
    objects: list[CatalogObject],
    count: int,
) -> tuple[CatalogObject, ...]:
    by_id = {item.object_id: item for item in objects}
    seen = {base.object_id, target.object_id}
    resolved: list[CatalogObject] = []
    for object_id in proposal.hard_negative_ids:
        item = by_id.get(object_id)
        if item is None or item.status != "active" or item.object_id in seen:
            continue
        resolved.append(item)
        seen.add(item.object_id)
        if len(resolved) >= count:
            return tuple(resolved)
    fallback = select_hard_negatives(base=base, target=target, objects=objects, count=count)
    for item in fallback:
        if item.object_id in seen:
            continue
        resolved.append(item)
        seen.add(item.object_id)
        if len(resolved) >= count:
            break
    return tuple(resolved)


def freeze_daily_puzzle(
    puzzle_date: date,
    eligible_pairs: list[CandidatePair],
    qualities: dict[str, PuzzleQuality],
    frozen_at: datetime | None = None,
) -> DailyPuzzle:
    accepted = [
        pair
        for pair in eligible_pairs
        if pair.pair_id in qualities and qualities[pair.pair_id].accepted
    ]
    if not accepted:
        raise ValueError("No accepted pairs are available for DailyPuzzle.")
    accepted = sorted(accepted, key=lambda item: item.pair_id)
    index = stable_index(puzzle_date.isoformat(), len(accepted))
    pair = accepted[index]
    quality = qualities[pair.pair_id]
    return DailyPuzzle(
        date=puzzle_date,
        pair_id=pair.pair_id,
        ref_version=quality.ref_version,
        frozen_at=frozen_at or datetime.now(timezone.utc),
    )


def stable_index(seed: str, modulo: int) -> int:
    if modulo <= 0:
        raise ValueError("modulo must be positive.")
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % modulo


def measured_difficulty_bucket(p50: float) -> str:
    if p50 < 0.20:
        return "hard"
    if p50 < 0.50:
        return "normal"
    return "easy"


def normalize_proposed_label(value: str) -> str:
    normalized = " ".join(value.replace("_", " ").strip().casefold().split())
    if not normalized:
        raise ValueError("proposal label must not be blank")
    if len(normalized) > 48:
        raise ValueError("proposal label must be 48 characters or fewer")
    return normalized


def normalize_pair_proposal_review_note(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) > 240:
        raise ValueError("proposal review note must be 240 characters or fewer")
    return normalized


def build_pair_proposal_key(
    base_label: str,
    target_label: str,
    base_object_id: str = "",
    target_object_id: str = "",
) -> str:
    return (
        f"{pair_proposal_subject_key(base_label, base_object_id)}"
        f"->{pair_proposal_subject_key(target_label, target_object_id)}"
    )


def pair_proposal_subject_key(label: str, object_id: str = "") -> str:
    if object_id:
        return f"object:{object_id}"
    return f"label:{normalize_proposed_label(label)}"


def lexical_semantic_distance(left: str, right: str) -> float:
    left_tokens = character_bigrams(left)
    right_tokens = character_bigrams(right)
    if not left_tokens or not right_tokens:
        return 1.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return 1.0 - (overlap / union)


def character_bigrams(value: str) -> set[str]:
    normalized = "".join(char for char in value.lower() if char.isalnum())
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def object_ref(obj: CatalogObject) -> dict[str, Any]:
    return {
        "object_id": obj.object_id,
        "canonical_label": obj.canonical_label,
        "aliases": list(obj.aliases),
    }
