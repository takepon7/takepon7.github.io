from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from gitai_phase0.puzzle import (
    CatalogObject,
    CurationPolicy,
    PairProposal,
    ShapeVector,
    build_pair_proposal_key,
    freeze_daily_puzzle,
    generate_candidate_pairs,
    normalize_proposed_label,
    seed_queue_entry_from_approved_proposal,
)
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository, SeedScoreRepository


def test_difficulty_prior_does_not_use_color() -> None:
    policy = CurationPolicy()
    base = catalog_object(
        object_id="red_ball",
        label="ball",
        colors=("red",),
        shape=ShapeVector(0.9, 0.1, 0.0, 0.0, 0.2),
    )
    same_shape_different_color = catalog_object(
        object_id="blue_ball",
        label="ball",
        colors=("blue",),
        shape=ShapeVector(0.9, 0.1, 0.0, 0.0, 0.2),
    )
    target = catalog_object(
        object_id="coin",
        label="coin",
        colors=("silver",),
        shape=ShapeVector(0.8, 0.1, 0.1, 0.0, 0.3),
    )
    assert policy.difficulty_prior(base, target) == policy.difficulty_prior(
        same_shape_different_color,
        target,
    )


def test_plausible_gate_rejects_far_silhouette() -> None:
    policy = CurationPolicy(plausible_shape_distance=0.4)
    round_object = catalog_object("ball", "ball", (), ShapeVector(1.0, 0.0, 0.0, 0.0, 0.1))
    flat_object = catalog_object("book", "book", (), ShapeVector(0.0, 0.2, 1.0, 0.0, 0.3))
    assert policy.is_plausible(round_object, flat_object) is False


def test_candidate_generation_freezes_hard_negatives() -> None:
    objects = ObjectCatalogRepository(Path("data/puzzle/object_catalog.json")).list()
    policy = CurationPolicy()
    first = generate_candidate_pairs(objects, policy)
    second = generate_candidate_pairs(objects, policy)
    pair = next(item for item in first if item.pair_id == "apple_to_baseball")
    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    assert pair.base.object_id == "apple"
    assert pair.target.object_id == "baseball"
    assert len(pair.hard_negatives) == 3
    assert "apple" not in [item.object_id for item in pair.hard_negatives]
    assert "baseball" not in [item.object_id for item in pair.hard_negatives]


def test_pair_proposal_evaluation_routes_candidate_review_and_rejection() -> None:
    catalog = ObjectCatalogRepository(Path("data/puzzle/object_catalog.json"))
    objects = catalog.list()
    policy = CurationPolicy()

    candidate = policy.evaluate_pair_proposal(
        base_label="apple",
        target_label="baseball",
        base=catalog.find_by_label("apple"),
        target=catalog.find_by_label("base ball"),
        objects=objects,
    )
    unknown = policy.evaluate_pair_proposal(
        base_label="dragonfruit",
        target_label="baseball",
        base=catalog.find_by_label("dragonfruit"),
        target=catalog.find_by_label("baseball"),
        objects=objects,
    )
    same = policy.evaluate_pair_proposal(
        base_label="apple",
        target_label="apple",
        base=catalog.find_by_label("apple"),
        target=catalog.find_by_label("apples"),
        objects=objects,
    )

    assert candidate.status == "candidate"
    assert candidate.difficulty_prior is not None
    assert [item.object_id for item in candidate.hard_negatives] == [
        "tennis_ball",
        "tomato",
        "orange",
    ]
    assert unknown.status == "needs_catalog_review"
    assert unknown.rejection_reasons == ("unknown_base_label",)
    assert same.status == "rejected"
    assert same.rejection_reasons == ("same_label",)


def test_proposed_label_normalization_is_strict_enough_for_review() -> None:
    assert normalize_proposed_label("  Tennis_Ball  ") == "tennis ball"

    try:
        normalize_proposed_label("   ")
    except ValueError as exc:
        assert "blank" in str(exc)
    else:
        raise AssertionError("blank proposal labels must be rejected")


def test_pair_proposal_key_prefers_catalog_identity_over_label_aliases() -> None:
    assert (
        build_pair_proposal_key(
            base_label="Apples",
            target_label="Base Ball",
            base_object_id="apple",
            target_object_id="baseball",
        )
        == "object:apple->object:baseball"
    )
    assert (
        build_pair_proposal_key(base_label="Dragon_Fruit", target_label="Base Ball")
        == "label:dragon fruit->label:base ball"
    )


def test_pair_proposal_review_requires_catalog_objects_for_approval() -> None:
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    proposal = PairProposal(
        proposal_id="proposal-1",
        pair_key="label:dragon fruit->object:car",
        user_id="curator",
        base_label="dragon fruit",
        target_label="car",
        base_object_id="",
        target_object_id="car",
        status="needs_catalog_review",
        rejection_reasons=("unknown_base_label",),
        difficulty_prior=None,
        hard_negative_ids=(),
        support_count=1,
        created_at=now,
        last_supported_at=now,
    )

    try:
        proposal.review(status="approved", reviewer_id="ops", note="looks fun", reviewed_at=now)
    except ValueError as exc:
        assert "known catalog objects" in str(exc)
    else:
        raise AssertionError("unknown object proposals must not be approved")

    rejected = proposal.review(status="rejected", reviewer_id="ops", note="needs catalog first", reviewed_at=now)
    assert rejected.status == "rejected"
    assert rejected.reviewer_id == "ops"
    assert rejected.review_note == "needs catalog first"
    assert rejected.reviewed_at == now


def test_approved_pair_proposal_becomes_seed_queue_entry() -> None:
    catalog = ObjectCatalogRepository(Path("data/puzzle/object_catalog.json"))
    objects = catalog.list()
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    proposal = PairProposal(
        proposal_id="proposal-1",
        pair_key="object:apple->object:baseball",
        user_id="curator",
        base_label="apple",
        target_label="base ball",
        base_object_id="apple",
        target_object_id="baseball",
        status="approved",
        rejection_reasons=(),
        difficulty_prior=0.22,
        hard_negative_ids=("tennis_ball", "tomato", "orange"),
        support_count=4,
        created_at=now,
        last_supported_at=now,
        reviewer_id="ops",
        review_note="seed next",
        reviewed_at=now,
    )

    entry = seed_queue_entry_from_approved_proposal(
        proposal=proposal,
        objects=objects,
        policy=CurationPolicy(),
    )

    assert entry.pair_id == "apple_to_baseball"
    assert entry.support_count == 4
    assert entry.base.object_id == "apple"
    assert entry.target.object_id == "baseball"
    assert [item.object_id for item in entry.hard_negatives] == [
        "tennis_ball",
        "tomato",
        "orange",
    ]
    assert entry.to_candidate_pair().to_pair_spec().pair_id == "apple_to_baseball"


def test_open_clip_seed_distribution_is_accepted() -> None:
    policy = CurationPolicy()
    refs = SeedScoreRepository(Path("data/scoring/seed_scores.json")).list()
    open_clip = next(item for item in refs if item.ref_version == "phase0-open-clip-tau30-2026-06-29")
    quality = policy.evaluate_seed_scores(open_clip)
    assert quality.accepted is True
    assert quality.spread >= policy.spread_floor
    assert quality.measured_difficulty == "hard"


def test_seed_score_repository_finds_compatible_ref_by_pair_and_model() -> None:
    refs = SeedScoreRepository(Path("data/scoring/seed_scores.json"))

    compatible = refs.find_compatible(
        pair_id="apple_to_baseball",
        model_version="open_clip:ViT-L-14:openai:fp32",
    )
    # chair_to_car is the one canonical pair that no real model could fool, so it
    # still has no open_clip-compatible SeedScore ref and must return None.
    missing = refs.find_compatible(
        pair_id="chair_to_car",
        model_version="open_clip:ViT-L-14:openai:fp32",
    )

    assert compatible is not None
    assert compatible.ref_version == "phase0-open-clip-tau30-2026-06-29"
    assert missing is None


def test_daily_puzzle_freeze_is_deterministic() -> None:
    objects = ObjectCatalogRepository(Path("data/puzzle/object_catalog.json")).list()
    policy = CurationPolicy()
    candidates = generate_candidate_pairs(objects, policy)
    refs = SeedScoreRepository(Path("data/scoring/seed_scores.json")).list()
    qualities = {
        quality.pair_id: quality
        for quality in (policy.evaluate_seed_scores(ref) for ref in refs)
        if quality.accepted and quality.ref_version == "phase0-open-clip-tau30-2026-06-29"
    }
    frozen_at = datetime(2026, 6, 29, tzinfo=timezone.utc)
    first = freeze_daily_puzzle(date(2026, 6, 29), candidates, qualities, frozen_at)
    second = freeze_daily_puzzle(date(2026, 6, 29), candidates, qualities, frozen_at)
    assert first == second
    assert first.pair_id == "apple_to_baseball"
    assert first.ref_version == "phase0-open-clip-tau30-2026-06-29"


def test_playtest_daily_pack_has_real_model_refs_and_heuristic_fallbacks() -> None:
    pairs = PairRepository(Path("data/scoring/pairs.json"))
    refs = SeedScoreRepository(Path("data/scoring/seed_scores.json"))
    daily = DailyPuzzleRepository(Path("data/puzzle/daily_puzzles.json"))
    policy = CurationPolicy()

    puzzles = daily.list()
    assert len(puzzles) >= 8
    assert daily.current(date(2026, 6, 29)).pair_id == "apple_to_baseball"
    assert daily.current(date(2026, 7, 4)).pair_id == "book_to_car"
    assert daily.latest().date == date(2026, 7, 6)
    assert daily.latest().pair_id == "apple_to_baseball"
    assert daily.latest().ref_version == "phase0-open-clip-tau30-2026-06-29"
    real_model_count = 0
    for puzzle in puzzles:
        pair = pairs.get(puzzle.pair_id)
        ref = refs.get(puzzle.ref_version)
        heuristic_ref = refs.find_compatible(puzzle.pair_id, "heuristic-color-shape-v1")
        quality = policy.evaluate_seed_scores(ref)
        assert ref.pair_id == pair.pair_id
        assert heuristic_ref is not None
        assert quality.accepted is True
        if ref.model_version != "heuristic-color-shape-v1":
            real_model_count += 1
    assert real_model_count == 6


def catalog_object(
    object_id: str,
    label: str,
    colors: tuple[str, ...],
    shape: ShapeVector,
) -> CatalogObject:
    return CatalogObject(
        object_id=object_id,
        canonical_label=label,
        aliases=(),
        shape_vec=shape,
        malleability=0.5,
        evocability=0.5,
        category="test",
        dominant_colors=colors,
        status="active",
        source="human_curated",
    )
