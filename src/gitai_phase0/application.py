from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import uuid
from typing import Any, Protocol

from PIL import Image

from gitai_phase0.commentary import (
    AppraisalComment,
    GeneratedAppraisalComment,
    build_appraisal_comment,
    is_safe_layer2_comment,
)
from gitai_phase0.cosmetics import CosmeticSpec, CosmeticUnlock, rewardable_cosmetics_for_submission
from gitai_phase0.competition import (
    DEFAULT_SEASON_ID,
    PlayerIdentity,
    SubmissionRecord,
    count_strokes,
    normalize_friend_code,
    normalize_season_id,
)
from gitai_phase0.domain import CaseSpec, DEFAULT_TEMPLATE_SET, Confidence, PairSpec, ScoreBucket
from gitai_phase0.ports import ImageModerator, JudgeModel, OcrScanner
from gitai_phase0.puzzle import (
    ApprovedPairSeedQueueEntry,
    CatalogObject,
    CurationPolicy,
    PairProposal,
    PairProposalReviewDecision,
    PairProposalStatus,
    build_pair_proposal_key,
    normalize_proposed_label,
    seed_queue_entry_from_approved_proposal,
)
from gitai_phase0.repositories import SeedScoreRef, image_fingerprint
from gitai_phase0.scoring import score_case


class PairLookup(Protocol):
    def get(self, pair_id: str) -> PairSpec:
        raise NotImplementedError


class ObjectCatalogLookup(Protocol):
    def list(self) -> list[CatalogObject]:
        raise NotImplementedError

    def find_by_label(self, label: str) -> CatalogObject | None:
        raise NotImplementedError


class SeedScoreLookup(Protocol):
    def get(self, ref_version: str) -> SeedScoreRef:
        raise NotImplementedError


class PairProposalStore(Protocol):
    def save(self, proposal: PairProposal) -> None:
        raise NotImplementedError

    def save_or_support(self, proposal: PairProposal) -> PairProposal:
        raise NotImplementedError

    def get(self, proposal_id: str) -> PairProposal:
        raise NotImplementedError

    def review(self, proposal: PairProposal) -> PairProposal:
        raise NotImplementedError

    def list(
        self,
        limit: int = 20,
        status: PairProposalStatus | None = None,
    ) -> list[PairProposal]:
        raise NotImplementedError


class SubmissionStore(Protocol):
    def save(self, record: SubmissionRecord) -> None:
        raise NotImplementedError

    def get(self, submission_id: str) -> SubmissionRecord:
        raise NotImplementedError

    def count_user_submissions(self, puzzle_date: date, season_id: str, user_id: str) -> int:
        raise NotImplementedError

    def rank_for(
        self,
        puzzle_date: date,
        submission_id: str,
        season_id: str = DEFAULT_SEASON_ID,
        kind: str = "score",
        friend_code: str = "",
    ) -> int | None:
        raise NotImplementedError

    def record_funny_vote(self, submission_id: str, voter_user_id: str) -> tuple[bool, int]:
        raise NotImplementedError


class AppraisalStore(Protocol):
    def get_cached_comment(self, submission_id: str) -> AppraisalComment | None:
        raise NotImplementedError

    def cache_comment(
        self,
        submission_id: str,
        user_id: str,
        comment: AppraisalComment,
        actor_version: str,
        cost_units: int,
        day: date,
        created_at: datetime | None = None,
    ) -> bool:
        raise NotImplementedError

    def daily_spend(self, day: date) -> int:
        raise NotImplementedError

    def user_daily_count(self, user_id: str, day: date) -> int:
        raise NotImplementedError

    def record_spend(
        self,
        submission_id: str,
        user_id: str,
        actor_version: str,
        cost_units: int,
        day: date,
        created_at: datetime | None = None,
    ) -> None:
        raise NotImplementedError


class CosmeticStore(Protocol):
    def unlocked_cosmetics(self, user_id: str, season_id: str) -> list[CosmeticUnlock]:
        raise NotImplementedError

    def unlock_cosmetics(
        self,
        user_id: str,
        season_id: str,
        cosmetics: tuple[CosmeticSpec, ...],
    ) -> list[CosmeticUnlock]:
        raise NotImplementedError


class PremiumAccessLookup(Protocol):
    def has_premium_access(self, user_id: str) -> bool:
        raise NotImplementedError


class SubmissionImageStore(Protocol):
    def save(self, submission_id: str, image: Image.Image) -> str:
        raise NotImplementedError

    def read(self, image_ref: str) -> bytes:
        raise NotImplementedError


class Layer2AppraisalActor(Protocol):
    actor_version: str
    estimated_cost_units: int

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment | None:
        raise NotImplementedError


@dataclass(frozen=True)
class DrawingVerification:
    accepted: bool
    distance: float
    reason: str


class DrawingVerifier(Protocol):
    def verify(
        self,
        image: Image.Image,
        pair: PairSpec,
        stroke_log: dict[str, Any] | None,
    ) -> DrawingVerification:
        raise NotImplementedError


@dataclass(frozen=True)
class ScoreSubmissionCommand:
    image: Image.Image
    pair_id: str
    ref_version: str
    stroke_log: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScoreSubmissionResult:
    score: int
    percentile: float
    raw: float
    confidences: Confidence
    bucket: ScoreBucket
    ocr_cheat: bool
    moderation: str
    model_version: str
    template_set_id: str
    tau: float


@dataclass(frozen=True)
class SubmitDrawingCommand:
    image: Image.Image
    pair_id: str
    ref_version: str
    puzzle_date: date
    user_id: str
    display_name: str
    stroke_log: dict[str, Any] | None = None
    friend_code: str = ""
    season_id: str = DEFAULT_SEASON_ID


@dataclass(frozen=True)
class SubmitDrawingResult:
    submission_id: str
    rank: int | None
    scored: ScoreSubmissionResult
    rewards: tuple[CosmeticUnlock, ...] = ()


@dataclass(frozen=True)
class SubmitPairProposalCommand:
    user_id: str
    base_label: str
    target_label: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class SubmitPairProposalResult:
    proposal: PairProposal
    base: CatalogObject | None
    target: CatalogObject | None
    hard_negatives: tuple[CatalogObject, ...]


@dataclass(frozen=True)
class ReviewPairProposalCommand:
    proposal_id: str
    reviewer_id: str
    status: PairProposalReviewDecision
    note: str = ""
    reviewed_at: datetime | None = None


@dataclass(frozen=True)
class ReviewPairProposalResult:
    proposal: PairProposal


@dataclass(frozen=True)
class BuildApprovedPairSeedQueueCommand:
    limit: int = 50
    hard_negative_count: int = 3


@dataclass(frozen=True)
class SkippedPairSeedQueueProposal:
    proposal_id: str
    pair_key: str
    reason: str


@dataclass(frozen=True)
class BuildApprovedPairSeedQueueResult:
    entries: tuple[ApprovedPairSeedQueueEntry, ...]
    skipped: tuple[SkippedPairSeedQueueProposal, ...] = ()


@dataclass(frozen=True)
class VoteForSubmissionCommand:
    submission_id: str
    voter_user_id: str


@dataclass(frozen=True)
class VoteForSubmissionResult:
    submission_id: str
    funny_votes: int
    accepted: bool


@dataclass(frozen=True)
class MintAppraisalCommentCommand:
    submission_id: str
    user_id: str
    mode: str = "on_demand"
    day: date | None = None


@dataclass(frozen=True)
class MintAppraisalCommentResult:
    submission_id: str
    comment: AppraisalComment
    status: str
    daily_spend: int
    daily_cap: int
    user_remaining: int


class ScoreSubmissionUseCase:
    def __init__(
        self,
        pairs: PairLookup,
        seed_scores: SeedScoreLookup,
        judge: JudgeModel,
        ocr: OcrScanner,
        moderator: ImageModerator,
    ) -> None:
        self._pairs = pairs
        self._seed_scores = seed_scores
        self._judge = judge
        self._ocr = ocr
        self._moderator = moderator

    def execute(self, command: ScoreSubmissionCommand) -> ScoreSubmissionResult:
        pair = self._pairs.get(command.pair_id)
        ref = self._seed_scores.get(command.ref_version)
        self._assert_ref_matches_runtime(pair, ref)

        case = CaseSpec(
            case_id="api_submission",
            image_path="",
            pair=pair,
            expected_quality="medium",
            expected_rank=0,
        )
        result = score_case(
            image=command.image,
            case=case,
            judge=self._judge,
            ocr=self._ocr,
            tau=ref.tau,
            template_set=DEFAULT_TEMPLATE_SET,
        )
        moderation = "flag" if self._moderator.moderate(command.image, case) == "flag" else "pass"
        percentile = ref.percentile_for(result.raw)
        return ScoreSubmissionResult(
            score=round(1000 * percentile),
            percentile=percentile,
            raw=result.raw,
            confidences=result.confidences,
            bucket=result.bucket,
            ocr_cheat=result.ocr_cheat,
            moderation=moderation,
            model_version=result.model_version,
            template_set_id=result.template_set_id,
            tau=result.tau,
        )

    def _assert_ref_matches_runtime(self, pair: PairSpec, ref: SeedScoreRef) -> None:
        if ref.pair_id != pair.pair_id:
            raise RefVersionConflict("ref_version does not belong to pair_id")
        if ref.model_version != self._judge.model_version:
            raise RefVersionConflict("ref_version model does not match active judge")
        if ref.template_set_id != DEFAULT_TEMPLATE_SET.template_set_id:
            raise RefVersionConflict("ref_version template set does not match active template set")


class RefVersionConflict(RuntimeError):
    pass


class DrawingVerificationFailed(RuntimeError):
    pass


class FunnyVoteRejected(RuntimeError):
    pass


class DailySubmissionLimitExceeded(RuntimeError):
    pass


class PairProposalReviewRejected(RuntimeError):
    pass


class SubmitDrawingUseCase:
    def __init__(
        self,
        pairs: PairLookup,
        scorer: ScoreSubmissionUseCase,
        submissions: SubmissionStore,
        drawing_verifier: DrawingVerifier,
        image_store: SubmissionImageStore,
        daily_submission_limit: int = 0,
        premium_user_ids: set[str] | None = None,
        premium_access: PremiumAccessLookup | None = None,
        cosmetics: CosmeticStore | None = None,
    ) -> None:
        self._pairs = pairs
        self._scorer = scorer
        self._submissions = submissions
        self._drawing_verifier = drawing_verifier
        self._image_store = image_store
        self._daily_submission_limit = max(0, daily_submission_limit)
        self._premium_user_ids = premium_user_ids or set()
        self._premium_access = premium_access
        self._cosmetics = cosmetics

    def execute(self, command: SubmitDrawingCommand) -> SubmitDrawingResult:
        user_id = sanitize_user_id(command.user_id)
        season_id = sanitize_season_id(command.season_id)
        has_premium_access = user_id in self._premium_user_ids or (
            self._premium_access.has_premium_access(user_id) if self._premium_access is not None else False
        )
        if (
            self._daily_submission_limit > 0
            and not has_premium_access
            and self._submissions.count_user_submissions(command.puzzle_date, season_id, user_id) >= self._daily_submission_limit
        ):
            raise DailySubmissionLimitExceeded("daily submission limit exceeded")
        pair = self._pairs.get(command.pair_id)
        verification = self._drawing_verifier.verify(
            image=command.image,
            pair=pair,
            stroke_log=command.stroke_log,
        )
        if not verification.accepted:
            raise DrawingVerificationFailed(verification.reason)
        scored = self._scorer.execute(
            ScoreSubmissionCommand(
                image=command.image,
                pair_id=command.pair_id,
                ref_version=command.ref_version,
                stroke_log=command.stroke_log,
            )
        )
        submission_id = uuid.uuid4().hex
        image_ref = self._image_store.save(submission_id, command.image)
        friend_code = normalize_friend_code(command.friend_code)
        record = SubmissionRecord(
            submission_id=submission_id,
            puzzle_date=command.puzzle_date,
            pair_id=command.pair_id,
            ref_version=command.ref_version,
            player=PlayerIdentity(
                user_id=user_id,
                display_name=sanitize_display_name(command.display_name),
            ),
            image_hash=image_fingerprint(command.image),
            stroke_count=count_strokes(command.stroke_log),
            score=scored.score,
            percentile=scored.percentile,
            raw=scored.raw,
            bucket=scored.bucket,
            ocr_cheat=scored.ocr_cheat,
            moderation=scored.moderation,
            model_version=scored.model_version,
            created_at=datetime.now(timezone.utc),
            season_id=season_id,
            image_ref=image_ref,
            friend_code=friend_code,
            stroke_log=command.stroke_log,
        )
        self._submissions.save(record)
        rewards: tuple[CosmeticUnlock, ...] = ()
        if self._cosmetics is not None:
            rewards = tuple(
                self._cosmetics.unlock_cosmetics(
                    user_id=user_id,
                    season_id=season_id,
                    cosmetics=rewardable_cosmetics_for_submission(record),
                )
            )
        return SubmitDrawingResult(
            submission_id=submission_id,
            rank=self._submissions.rank_for(
                command.puzzle_date,
                submission_id,
                season_id=season_id,
                kind="score",
            ),
            scored=scored,
            rewards=rewards,
        )


class SubmitPairProposalUseCase:
    def __init__(
        self,
        object_catalog: ObjectCatalogLookup,
        proposals: PairProposalStore,
        policy: CurationPolicy | None = None,
    ) -> None:
        self._object_catalog = object_catalog
        self._proposals = proposals
        self._policy = policy or CurationPolicy()

    def execute(self, command: SubmitPairProposalCommand) -> SubmitPairProposalResult:
        base_label = normalize_proposed_label(command.base_label)
        target_label = normalize_proposed_label(command.target_label)
        objects = self._object_catalog.list()
        evaluation = self._policy.evaluate_pair_proposal(
            base_label=base_label,
            target_label=target_label,
            base=self._object_catalog.find_by_label(base_label),
            target=self._object_catalog.find_by_label(target_label),
            objects=objects,
        )
        created_at = command.created_at or datetime.now(timezone.utc)
        proposal = PairProposal(
            proposal_id=uuid.uuid4().hex,
            pair_key=build_pair_proposal_key(
                base_label=base_label,
                target_label=target_label,
                base_object_id=evaluation.base.object_id if evaluation.base else "",
                target_object_id=evaluation.target.object_id if evaluation.target else "",
            ),
            user_id=sanitize_user_id(command.user_id),
            base_label=base_label,
            target_label=target_label,
            base_object_id=evaluation.base.object_id if evaluation.base else "",
            target_object_id=evaluation.target.object_id if evaluation.target else "",
            status=evaluation.status,
            rejection_reasons=evaluation.rejection_reasons,
            difficulty_prior=evaluation.difficulty_prior,
            hard_negative_ids=tuple(item.object_id for item in evaluation.hard_negatives),
            support_count=1,
            created_at=created_at,
            last_supported_at=created_at,
        )
        proposal = self._proposals.save_or_support(proposal)
        return SubmitPairProposalResult(
            proposal=proposal,
            base=evaluation.base,
            target=evaluation.target,
            hard_negatives=evaluation.hard_negatives,
        )


class ReviewPairProposalUseCase:
    def __init__(self, proposals: PairProposalStore) -> None:
        self._proposals = proposals

    def execute(self, command: ReviewPairProposalCommand) -> ReviewPairProposalResult:
        proposal = self._proposals.get(command.proposal_id)
        try:
            reviewed = proposal.review(
                status=command.status,
                reviewer_id=sanitize_user_id(command.reviewer_id),
                note=command.note,
                reviewed_at=command.reviewed_at,
            )
        except ValueError as exc:
            raise PairProposalReviewRejected(str(exc)) from exc
        return ReviewPairProposalResult(proposal=self._proposals.review(reviewed))


class BuildApprovedPairSeedQueueUseCase:
    def __init__(
        self,
        object_catalog: ObjectCatalogLookup,
        proposals: PairProposalStore,
        policy: CurationPolicy | None = None,
    ) -> None:
        self._object_catalog = object_catalog
        self._proposals = proposals
        self._policy = policy or CurationPolicy()

    def execute(
        self,
        command: BuildApprovedPairSeedQueueCommand | None = None,
    ) -> BuildApprovedPairSeedQueueResult:
        command = command or BuildApprovedPairSeedQueueCommand()
        objects = self._object_catalog.list()
        entries: list[ApprovedPairSeedQueueEntry] = []
        skipped: list[SkippedPairSeedQueueProposal] = []
        proposals = self._proposals.list(
            limit=max(1, min(command.limit, 200)),
            status="approved",
        )
        for proposal in proposals:
            try:
                entries.append(
                    seed_queue_entry_from_approved_proposal(
                        proposal=proposal,
                        objects=objects,
                        policy=self._policy,
                        hard_negative_count=max(1, command.hard_negative_count),
                    )
                )
            except ValueError as exc:
                skipped.append(
                    SkippedPairSeedQueueProposal(
                        proposal_id=proposal.proposal_id,
                        pair_key=proposal.pair_key,
                        reason=str(exc),
                    )
                )
        entries.sort(key=lambda item: (-item.support_count, item.pair_id, item.proposal_id))
        return BuildApprovedPairSeedQueueResult(
            entries=tuple(entries),
            skipped=tuple(skipped),
        )


class VoteForSubmissionUseCase:
    def __init__(self, submissions: SubmissionStore) -> None:
        self._submissions = submissions

    def execute(self, command: VoteForSubmissionCommand) -> VoteForSubmissionResult:
        voter_user_id = sanitize_user_id(command.voter_user_id)
        submission = self._submissions.get(command.submission_id)
        if submission.player.user_id == voter_user_id:
            raise FunnyVoteRejected("cannot vote for your own submission")
        accepted, funny_votes = self._submissions.record_funny_vote(command.submission_id, voter_user_id)
        return VoteForSubmissionResult(
            submission_id=command.submission_id,
            funny_votes=funny_votes,
            accepted=accepted,
        )


class MintAppraisalCommentUseCase:
    HERO_PERCENTILE_FLOOR = 0.95
    HERO_SPEND_USER_ID = "__hero_appraisal__"

    def __init__(
        self,
        pairs: PairLookup,
        submissions: SubmissionStore,
        submission_images: SubmissionImageStore,
        appraisals: AppraisalStore,
        actor: Layer2AppraisalActor,
        daily_cap_units: int,
        user_daily_limit: int,
    ) -> None:
        self._pairs = pairs
        self._submissions = submissions
        self._submission_images = submission_images
        self._appraisals = appraisals
        self._actor = actor
        self._daily_cap_units = daily_cap_units
        self._user_daily_limit = user_daily_limit

    def execute(self, command: MintAppraisalCommentCommand) -> MintAppraisalCommentResult:
        user_id = sanitize_user_id(command.user_id)
        day = command.day or datetime.now(timezone.utc).date()
        submission = self._submissions.get(command.submission_id)
        pair = self._pairs.get(submission.pair_id)
        fallback = build_appraisal_comment(
            pair=pair,
            bucket=submission.bucket,
            score=submission.score,
            cy=0.0,
            cx=0.0,
            ocr_cheat=submission.ocr_cheat,
            moderation=submission.moderation,
            selector=submission.submission_id,
        )

        cached = self._appraisals.get_cached_comment(submission.submission_id)
        if cached is not None:
            return self._result(submission.submission_id, cached, "cached", user_id, day)
        is_hero = command.mode == "hero"
        if is_hero and not self._is_hero_eligible(submission):
            return self._result(submission.submission_id, fallback, "fallback_hero_gate", user_id, day)
        if submission.ocr_cheat or submission.moderation != "pass":
            return self._result(submission.submission_id, fallback, "fallback_safety", user_id, day)
        if not is_hero and self._appraisals.user_daily_count(user_id, day) >= self._user_daily_limit:
            return self._result(submission.submission_id, fallback, "fallback_user_quota", user_id, day)

        cost_units = max(1, int(self._actor.estimated_cost_units))
        if self._appraisals.daily_spend(day) + cost_units > self._daily_cap_units:
            return self._result(submission.submission_id, fallback, "fallback_budget", user_id, day)

        try:
            image_bytes = self._submission_images.read(submission.image_ref)
            generated = self._actor.generate(submission=submission, pair=pair, image_bytes=image_bytes)
        except (FileNotFoundError, KeyError):
            generated = None
        if generated is None:
            return self._result(submission.submission_id, fallback, "fallback_unavailable", user_id, day)
        if not is_safe_layer2_comment(generated.comment):
            spend_user_id = self.HERO_SPEND_USER_ID if is_hero else user_id
            self._appraisals.record_spend(
                submission_id=submission.submission_id,
                user_id=spend_user_id,
                actor_version=generated.actor_version,
                cost_units=generated.cost_units,
                day=day,
            )
            return self._result(submission.submission_id, fallback, "fallback_output_filter", user_id, day)

        spend_user_id = self.HERO_SPEND_USER_ID if is_hero else user_id
        inserted = self._appraisals.cache_comment(
            submission_id=submission.submission_id,
            user_id=spend_user_id,
            comment=generated.comment,
            actor_version=generated.actor_version,
            cost_units=generated.cost_units,
            day=day,
        )
        return self._result(
            submission.submission_id,
            generated.comment,
            "minted" if inserted else "cached",
            user_id,
            day,
        )

    def _result(
        self,
        submission_id: str,
        comment: AppraisalComment,
        status: str,
        user_id: str,
        day: date,
    ) -> MintAppraisalCommentResult:
        return MintAppraisalCommentResult(
            submission_id=submission_id,
            comment=comment,
            status=status,
            daily_spend=self._appraisals.daily_spend(day),
            daily_cap=self._daily_cap_units,
            user_remaining=max(0, self._user_daily_limit - self._appraisals.user_daily_count(user_id, day)),
        )

    def _is_hero_eligible(self, submission: SubmissionRecord) -> bool:
        return (
            submission.percentile >= self.HERO_PERCENTILE_FLOOR
            and not submission.ocr_cheat
            and submission.moderation == "pass"
        )


def sanitize_display_name(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return "guest"
    return cleaned[:24]


def sanitize_user_id(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "local-player"
    return cleaned[:96]


def sanitize_season_id(value: str) -> str:
    return normalize_season_id(value) or DEFAULT_SEASON_ID
