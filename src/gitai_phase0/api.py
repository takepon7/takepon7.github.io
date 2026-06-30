from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import date, datetime, timezone
from io import BytesIO
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image

from gitai_phase0.application import (
    BuildApprovedPairSeedQueueCommand,
    BuildApprovedPairSeedQueueUseCase,
    DailySubmissionLimitExceeded,
    DrawingVerificationFailed,
    FunnyVoteRejected,
    MintAppraisalCommentCommand,
    MintAppraisalCommentUseCase,
    PairProposalReviewRejected,
    ReportContentCommand,
    ReportContentUseCase,
    RefVersionConflict,
    ReviewPairProposalCommand,
    ReviewPairProposalUseCase,
    ScoreSubmissionCommand,
    ScoreSubmissionUseCase,
    SubmitDrawingCommand,
    SubmitDrawingUseCase,
    SubmitPairProposalCommand,
    SubmitPairProposalUseCase,
    VoteForSubmissionCommand,
    VoteForSubmissionUseCase,
    sanitize_user_id,
)
from gitai_phase0.cli import build_judge
from gitai_phase0.commentary import AppraisalComment, build_appraisal_comment
from gitai_phase0.commentary_repositories import SqliteAppraisalRepository
from gitai_phase0.cosmetic_repositories import SqliteCosmeticRepository
from gitai_phase0.cosmetics import CosmeticUnlock, default_cosmetics
from gitai_phase0.competition import LeaderboardKind, SeasonSpec, normalize_friend_code, normalize_season_id
from gitai_phase0.competition_repositories import JsonSeedGhostRepository, SqliteSubmissionRepository
from gitai_phase0.drawing_verification import CanvasStrokeReplayVerifier
from gitai_phase0.entitlement_repositories import SqliteEntitlementRepository
from gitai_phase0.layer2_actors import build_layer2_actor_from_env
from gitai_phase0.moderation import ImageFingerprintModerator, NullImageModerator
from gitai_phase0.ocr import NullOcrScanner, TesseractOcrScanner
from gitai_phase0.puzzle import CatalogObject, PairProposalReviewDecision, PairProposalStatus
from gitai_phase0.puzzle_repositories import ObjectCatalogRepository, SqlitePairProposalRepository
from gitai_phase0.repositories import (
    ImageFingerprintOcrScanner,
    DailyPuzzleRepository,
    PairRepository,
    SeedScoreRepository,
    image_fingerprint,
)
from gitai_phase0.share_card import build_share_card
from gitai_phase0.submission_images import LocalSubmissionImageStore


SUBMISSION_RATE_LIMIT = (5, 60)
FUNNY_VOTE_RATE_LIMIT = (30, 60)
CONTENT_REPORT_RATE_LIMIT = (10, 60)
PAIR_PROPOSAL_RATE_LIMIT = (10, 60)
DEFAULT_CORS_ORIGINS = ",".join(
    (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    )
)
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}


class ScoreRequest(BaseModel):
    image_b64: str
    pair_id: str
    ref_version: str
    stroke_log: dict[str, Any] | None = None


class SubmitRequest(ScoreRequest):
    puzzle_date: str | None = None
    user_id: str = "local-player"
    display_name: str = "guest"
    friend_code: str = ""


class FunnyVoteRequest(BaseModel):
    submission_id: str
    user_id: str = "local-player"


class ContentReportRequest(BaseModel):
    submission_id: str
    user_id: str = "local-player"
    reason: str = Field(default="other", pattern="^(unsafe|personal_info|rights|spam|other)$")
    note: str = Field(default="", max_length=240)


class AppraisalCommentRequest(BaseModel):
    submission_id: str
    user_id: str = "local-player"
    mode: str = Field(default="on_demand", pattern="^(on_demand|hero)$")


class PremiumRedeemRequest(BaseModel):
    user_id: str = "local-player"
    code: str


class PairProposalRequest(BaseModel):
    user_id: str = "local-player"
    base_label: str = Field(min_length=1, max_length=64)
    target_label: str = Field(min_length=1, max_length=64)


class PairProposalReviewRequest(BaseModel):
    reviewer_id: str = "operator"
    status: str = Field(pattern="^(approved|needs_catalog_review|rejected)$")
    note: str = Field(default="", max_length=240)


class ConfidenceResponse(BaseModel):
    Cy: float
    Cx: float
    negs: list[float]


class FlagsResponse(BaseModel):
    ocr_cheat: bool
    moderation: str = Field(pattern="^(pass|flag)$")


class AppraisalCommentResponse(BaseModel):
    line: str
    mood: str
    source: str
    template_id: str


class CosmeticResponse(BaseModel):
    cosmetic_id: str
    kind: str
    label: str
    colors: list[str]
    newly_unlocked: bool = False


class ScoreResponse(BaseModel):
    score: int
    percentile: float
    raw: float
    confidences: ConfidenceResponse
    bucket: str
    flags: FlagsResponse
    model_version: str
    template_set_id: str
    tau: float
    computed_at: str
    comment: AppraisalCommentResponse


class DailyPuzzleResponse(BaseModel):
    date: str
    season_id: str
    season_label: str
    pair_id: str
    ref_version: str
    base: dict[str, Any]
    target: dict[str, Any]
    hard_negatives: list[dict[str, Any]]


class DailyPuzzleSummaryResponse(BaseModel):
    date: str
    pair_id: str
    base: dict[str, Any]
    target: dict[str, Any]
    current: bool = False


class DailyPuzzlesResponse(BaseModel):
    season_id: str
    season_label: str
    current_date: str
    entries: list[DailyPuzzleSummaryResponse]


class SubmissionResponse(BaseModel):
    submission_id: str
    season_id: str
    rank: int | None
    score: int
    percentile: float
    raw: float
    confidences: ConfidenceResponse
    bucket: str
    flags: FlagsResponse
    model_version: str
    template_set_id: str
    tau: float
    computed_at: str
    comment: AppraisalCommentResponse
    rewards: list[CosmeticResponse] = Field(default_factory=list)


class LeaderboardEntryResponse(BaseModel):
    rank: int
    submission_id: str
    season_id: str
    user_id: str
    display_name: str
    score: int
    percentile: float
    raw: float
    bucket: str
    stroke_count: int
    created_at: str
    friend_code: str = ""
    funny_votes: int = 0


class LeaderboardResponse(BaseModel):
    date: str
    season_id: str
    season_label: str
    kind: str
    entries: list[LeaderboardEntryResponse]


class GhostResponse(BaseModel):
    date: str
    season_id: str
    season_label: str
    kind: str
    rank: int
    submission_id: str
    display_name: str
    score: int
    funny_votes: int = 0
    bucket: str
    image_b64: str
    stroke_log: dict[str, Any] | None = None


class FunnyVoteResponse(BaseModel):
    submission_id: str
    funny_votes: int
    accepted: bool


class ContentReportResponse(BaseModel):
    report_id: str
    submission_id: str
    report_count: int
    status: str


class AppraisalCommentMintResponse(BaseModel):
    submission_id: str
    comment: AppraisalCommentResponse
    status: str
    daily_spend: int
    daily_cap: int
    user_remaining: int


class CosmeticsResponse(BaseModel):
    user_id: str
    season_id: str
    cosmetics: list[CosmeticResponse]


class PremiumResponse(BaseModel):
    user_id: str
    premium: bool
    source: str


class PremiumRedeemResponse(PremiumResponse):
    code: str
    status: str


class PairProposalResponse(BaseModel):
    proposal_id: str
    pair_key: str
    user_id: str
    base_label: str
    target_label: str
    base: dict[str, Any] | None
    target: dict[str, Any] | None
    status: str
    rejection_reasons: list[str]
    difficulty_prior: float | None
    hard_negatives: list[dict[str, Any]]
    support_count: int
    created_at: str
    last_supported_at: str
    reviewer_id: str = ""
    review_note: str = ""
    reviewed_at: str | None = None


class PairProposalsResponse(BaseModel):
    entries: list[PairProposalResponse]


class PairSeedQueueEntryResponse(BaseModel):
    proposal_id: str
    pair_key: str
    pair_id: str
    base: dict[str, Any]
    target: dict[str, Any]
    hard_negatives: list[dict[str, Any]]
    difficulty_prior: float
    support_count: int
    reviewer_id: str
    review_note: str
    reviewed_at: str | None
    status: str


class PairSeedQueueSkippedResponse(BaseModel):
    proposal_id: str
    pair_key: str
    reason: str


class PairSeedQueueResponse(BaseModel):
    entries: list[PairSeedQueueEntryResponse]
    skipped: list[PairSeedQueueSkippedResponse] = Field(default_factory=list)


class AppState:
    def __init__(
        self,
        pairs: PairRepository,
        seed_scores: SeedScoreRepository,
        daily_puzzles: DailyPuzzleRepository,
        object_catalog: ObjectCatalogRepository,
        pair_proposals: SqlitePairProposalRepository,
        submissions: SqliteSubmissionRepository,
        submission_images,
        appraisals,
        cosmetics,
        entitlements,
        appraisal_actor,
        daily_llm_spend_cap: int,
        user_daily_comment_limit: int,
        daily_submission_limit: int,
        premium_user_ids: set[str],
        season: SeasonSpec,
        drawing_verifier,
        judge,
        ocr,
        moderator,
    ) -> None:
        self.pairs = pairs
        self.seed_scores = seed_scores
        self.daily_puzzles = daily_puzzles
        self.object_catalog = object_catalog
        self.pair_proposals = pair_proposals
        self.submissions = submissions
        self.submission_images = submission_images
        self.appraisals = appraisals
        self.cosmetics = cosmetics
        self.entitlements = entitlements
        self.appraisal_actor = appraisal_actor
        self.daily_llm_spend_cap = daily_llm_spend_cap
        self.user_daily_comment_limit = user_daily_comment_limit
        self.daily_submission_limit = daily_submission_limit
        self.premium_user_ids = premium_user_ids
        self.season = season
        self.drawing_verifier = drawing_verifier
        self.judge = judge
        self.ocr = ocr
        self.moderator = moderator


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI(title="gitai scoring service", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("GITAI_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.gitai = state or build_state_from_env()

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        cache_control = cache_control_for_path(request.url.path)
        if cache_control:
            response.headers.setdefault("Cache-Control", cache_control)
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        service: AppState = app.state.gitai
        return {
            "status": "ok",
            "model_version": service.judge.model_version,
            "season_id": service.season.season_id,
            "season_label": service.season.label,
        }

    @app.get("/v1/daily-puzzles", response_model=DailyPuzzlesResponse)
    def daily_puzzles() -> DailyPuzzlesResponse:
        service: AppState = app.state.gitai
        today = runtime_today()
        try:
            current = service.daily_puzzles.current(today)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        entries: list[DailyPuzzleSummaryResponse] = []
        for puzzle in service.daily_puzzles.available_until(today):
            try:
                pair = service.pairs.get(puzzle.pair_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            entries.append(
                DailyPuzzleSummaryResponse(
                    date=puzzle.date.isoformat(),
                    pair_id=puzzle.pair_id,
                    base=object_label_payload(pair.base),
                    target=object_label_payload(pair.target),
                    current=puzzle.date == current.date,
                )
            )
        return DailyPuzzlesResponse(
            season_id=service.season.season_id,
            season_label=service.season.label,
            current_date=current.date.isoformat(),
            entries=entries,
        )

    @app.get("/v1/daily-puzzle", response_model=DailyPuzzleResponse)
    def daily_puzzle(date_: str | None = Query(default=None, alias="date")) -> DailyPuzzleResponse:
        service: AppState = app.state.gitai
        try:
            puzzle = puzzle_for_query(service, date_)
            pair = service.pairs.get(puzzle.pair_id)
            ref = select_daily_ref(service, puzzle, allow_env_override=date_ is None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if ref.pair_id != pair.pair_id:
            raise HTTPException(status_code=409, detail="daily ref_version does not belong to pair_id")
        if ref.model_version != service.judge.model_version:
            raise HTTPException(status_code=409, detail="daily ref_version model does not match active judge")
        return DailyPuzzleResponse(
            date=puzzle.date.isoformat(),
            season_id=service.season.season_id,
            season_label=service.season.label,
            pair_id=puzzle.pair_id,
            ref_version=ref.ref_version,
            base=object_label_payload(pair.base),
            target=object_label_payload(pair.target),
            hard_negatives=[object_label_payload(item) for item in pair.hard_negatives],
        )

    @app.post("/v1/score", response_model=ScoreResponse)
    def score(request: ScoreRequest) -> ScoreResponse:
        service: AppState = app.state.gitai
        try:
            image = Image.open(BytesIO(b64decode(request.image_b64))).convert("RGBA")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="image_b64 is not a valid image") from exc

        usecase = ScoreSubmissionUseCase(
            pairs=service.pairs,
            seed_scores=service.seed_scores,
            judge=service.judge,
            ocr=service.ocr,
            moderator=service.moderator,
        )
        try:
            pair = service.pairs.get(request.pair_id)
            result = usecase.execute(
                ScoreSubmissionCommand(
                    image=image,
                    pair_id=request.pair_id,
                    ref_version=request.ref_version,
                    stroke_log=request.stroke_log,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RefVersionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return ScoreResponse(
            score=result.score,
            percentile=result.percentile,
            raw=result.raw,
            confidences=ConfidenceResponse(
                Cy=result.confidences.Cy,
                Cx=result.confidences.Cx,
                negs=list(result.confidences.negs),
            ),
            bucket=result.bucket,
            flags=FlagsResponse(ocr_cheat=result.ocr_cheat, moderation=result.moderation),
            model_version=result.model_version,
            template_set_id=result.template_set_id,
            tau=result.tau,
            computed_at=datetime.now(timezone.utc).isoformat(),
            comment=comment_payload(
                build_appraisal_comment(
                    pair=pair,
                    bucket=result.bucket,
                    score=result.score,
                    cy=result.confidences.Cy,
                    cx=result.confidences.Cx,
                    ocr_cheat=result.ocr_cheat,
                    moderation=result.moderation,
                    selector=image_fingerprint(image),
                )
            ),
        )

    @app.post("/v1/submissions", response_model=SubmissionResponse)
    def submit(request: SubmitRequest) -> SubmissionResponse:
        service: AppState = app.state.gitai
        enforce_rate_limit(
            submissions=service.submissions,
            actor_id=request.user_id,
            action="submit",
            rule=SUBMISSION_RATE_LIMIT,
        )
        try:
            image = Image.open(BytesIO(b64decode(request.image_b64))).convert("RGBA")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="image_b64 is not a valid image") from exc
        try:
            puzzle_date = date.fromisoformat(request.puzzle_date) if request.puzzle_date else service.daily_puzzles.current(runtime_today()).date
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="puzzle_date is not a valid ISO date") from exc
        scorer = ScoreSubmissionUseCase(
            pairs=service.pairs,
            seed_scores=service.seed_scores,
            judge=service.judge,
            ocr=service.ocr,
            moderator=service.moderator,
        )
        submitter = SubmitDrawingUseCase(
            pairs=service.pairs,
            scorer=scorer,
            submissions=service.submissions,
            drawing_verifier=service.drawing_verifier,
            image_store=service.submission_images,
            daily_submission_limit=service.daily_submission_limit,
            premium_user_ids=service.premium_user_ids,
            premium_access=service.entitlements,
            cosmetics=service.cosmetics,
        )
        try:
            result = submitter.execute(
                SubmitDrawingCommand(
                    image=image,
                    pair_id=request.pair_id,
                    ref_version=request.ref_version,
                    puzzle_date=puzzle_date,
                    user_id=request.user_id,
                    display_name=request.display_name,
                    stroke_log=request.stroke_log,
                    friend_code=request.friend_code,
                    season_id=service.season.season_id,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RefVersionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DrawingVerificationFailed as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DailySubmissionLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

        scored = result.scored
        pair = service.pairs.get(request.pair_id)
        return SubmissionResponse(
            submission_id=result.submission_id,
            season_id=service.season.season_id,
            rank=result.rank,
            score=scored.score,
            percentile=scored.percentile,
            raw=scored.raw,
            confidences=ConfidenceResponse(
                Cy=scored.confidences.Cy,
                Cx=scored.confidences.Cx,
                negs=list(scored.confidences.negs),
            ),
            bucket=scored.bucket,
            flags=FlagsResponse(ocr_cheat=scored.ocr_cheat, moderation=scored.moderation),
            model_version=scored.model_version,
            template_set_id=scored.template_set_id,
            tau=scored.tau,
            computed_at=datetime.now(timezone.utc).isoformat(),
            comment=comment_payload(
                build_appraisal_comment(
                    pair=pair,
                    bucket=scored.bucket,
                    score=scored.score,
                    cy=scored.confidences.Cy,
                    cx=scored.confidences.Cx,
                    ocr_cheat=scored.ocr_cheat,
                    moderation=scored.moderation,
                    selector=result.submission_id,
                )
            ),
            rewards=[cosmetic_payload(item) for item in result.rewards],
        )

    @app.get("/v1/leaderboard", response_model=LeaderboardResponse)
    def leaderboard(
        date_: str | None = Query(default=None, alias="date"),
        kind: str = Query(default="score"),
        friend_code: str = Query(default=""),
        season_id: str | None = Query(default=None),
        limit: int = Query(default=20),
    ) -> LeaderboardResponse:
        service: AppState = app.state.gitai
        leaderboard_kind = parse_leaderboard_kind(kind)
        leaderboard_friend_code = require_friend_code_for_kind(leaderboard_kind, friend_code)
        leaderboard_season_id = parse_season_id_query(service, season_id)
        try:
            puzzle_date = date.fromisoformat(date_) if date_ else service.daily_puzzles.current(runtime_today()).date
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date is not a valid ISO date") from exc
        entries = service.submissions.leaderboard(
            puzzle_date=puzzle_date,
            season_id=leaderboard_season_id,
            limit=max(1, min(limit, 100)),
            kind=leaderboard_kind,
            friend_code=leaderboard_friend_code,
        )
        return LeaderboardResponse(
            date=puzzle_date.isoformat(),
            season_id=leaderboard_season_id,
            season_label=season_label_for_response(service, leaderboard_season_id),
            kind=leaderboard_kind,
            entries=[
                LeaderboardEntryResponse(
                    rank=entry.rank,
                    submission_id=entry.submission_id,
                    season_id=entry.season_id,
                    user_id=entry.user_id,
                    display_name=entry.display_name,
                    score=entry.score,
                    percentile=entry.percentile,
                    raw=entry.raw,
                    bucket=entry.bucket,
                    stroke_count=entry.stroke_count,
                    created_at=entry.created_at.isoformat(),
                    friend_code=entry.friend_code,
                    funny_votes=entry.funny_votes,
                )
                for entry in entries
            ],
        )

    @app.get("/v1/ghost", response_model=GhostResponse)
    def ghost(
        date_: str | None = Query(default=None, alias="date"),
        kind: str = Query(default="score"),
        friend_code: str = Query(default=""),
        season_id: str | None = Query(default=None),
    ) -> GhostResponse:
        service: AppState = app.state.gitai
        leaderboard_kind = parse_leaderboard_kind(kind)
        leaderboard_friend_code = require_friend_code_for_kind(leaderboard_kind, friend_code)
        ghost_season_id = parse_season_id_query(service, season_id)
        try:
            puzzle_date = date.fromisoformat(date_) if date_ else service.daily_puzzles.current(runtime_today()).date
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date is not a valid ISO date") from exc
        entries = service.submissions.leaderboard(
            puzzle_date=puzzle_date,
            season_id=ghost_season_id,
            limit=1,
            kind=leaderboard_kind,
            friend_code=leaderboard_friend_code,
        )
        if not entries:
            raise HTTPException(status_code=404, detail="ghost is not available")
        entry = entries[0]
        try:
            image_bytes = service.submission_images.read(entry.image_ref)
            record = service.submissions.get(entry.submission_id)
        except (FileNotFoundError, KeyError) as exc:
            raise HTTPException(status_code=404, detail="ghost image is not available") from exc
        return GhostResponse(
            date=puzzle_date.isoformat(),
            season_id=ghost_season_id,
            season_label=season_label_for_response(service, ghost_season_id),
            kind=leaderboard_kind,
            rank=entry.rank,
            submission_id=entry.submission_id,
            display_name=entry.display_name,
            score=entry.score,
            funny_votes=entry.funny_votes,
            bucket=entry.bucket,
            image_b64=b64encode(image_bytes).decode("ascii"),
            stroke_log=record.stroke_log,
        )

    @app.post("/v1/funny-votes", response_model=FunnyVoteResponse)
    def funny_vote(request: FunnyVoteRequest) -> FunnyVoteResponse:
        service: AppState = app.state.gitai
        enforce_rate_limit(
            submissions=service.submissions,
            actor_id=request.user_id,
            action="funny_vote",
            rule=FUNNY_VOTE_RATE_LIMIT,
        )
        usecase = VoteForSubmissionUseCase(submissions=service.submissions)
        try:
            result = usecase.execute(
                VoteForSubmissionCommand(
                    submission_id=request.submission_id,
                    voter_user_id=request.user_id,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FunnyVoteRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FunnyVoteResponse(
            submission_id=result.submission_id,
            funny_votes=result.funny_votes,
            accepted=result.accepted,
        )

    @app.post("/v1/content-reports", response_model=ContentReportResponse)
    def content_report(request: ContentReportRequest) -> ContentReportResponse:
        service: AppState = app.state.gitai
        enforce_rate_limit(
            submissions=service.submissions,
            actor_id=request.user_id,
            action="content_report",
            rule=CONTENT_REPORT_RATE_LIMIT,
        )
        usecase = ReportContentUseCase(submissions=service.submissions)
        try:
            result = usecase.execute(
                ReportContentCommand(
                    submission_id=request.submission_id,
                    reporter_user_id=request.user_id,
                    reason=request.reason,
                    note=request.note,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ContentReportResponse(
            report_id=result.report_id,
            submission_id=result.submission_id,
            report_count=result.report_count,
            status=result.status,
        )

    @app.post("/v1/appraisal-comments", response_model=AppraisalCommentMintResponse)
    def appraisal_comment(request: AppraisalCommentRequest) -> AppraisalCommentMintResponse:
        service: AppState = app.state.gitai
        usecase = MintAppraisalCommentUseCase(
            pairs=service.pairs,
            submissions=service.submissions,
            submission_images=service.submission_images,
            appraisals=service.appraisals,
            actor=service.appraisal_actor,
            daily_cap_units=service.daily_llm_spend_cap,
            user_daily_limit=service.user_daily_comment_limit,
        )
        try:
            result = usecase.execute(
                MintAppraisalCommentCommand(
                    submission_id=request.submission_id,
                    user_id=request.user_id,
                    mode=request.mode,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return AppraisalCommentMintResponse(
            submission_id=result.submission_id,
            comment=comment_payload(result.comment),
            status=result.status,
            daily_spend=result.daily_spend,
            daily_cap=result.daily_cap,
            user_remaining=result.user_remaining,
        )

    @app.get("/v1/cosmetics", response_model=CosmeticsResponse)
    def cosmetics(user_id: str = Query(default="local-player"), season_id: str | None = Query(default=None)) -> CosmeticsResponse:
        service: AppState = app.state.gitai
        viewer_id = sanitize_user_id(user_id)
        cosmetic_season_id = parse_season_id_query(service, season_id)
        now = datetime.now(timezone.utc)
        unlocks = list(default_cosmetics(viewer_id, cosmetic_season_id, now))
        unlocks.extend(service.cosmetics.unlocked_cosmetics(viewer_id, cosmetic_season_id))
        return CosmeticsResponse(
            user_id=viewer_id,
            season_id=cosmetic_season_id,
            cosmetics=[cosmetic_payload(item) for item in dedupe_cosmetic_unlocks(unlocks)],
        )

    @app.get("/v1/premium", response_model=PremiumResponse)
    def premium(user_id: str = Query(default="local-player")) -> PremiumResponse:
        service: AppState = app.state.gitai
        viewer_id = sanitize_user_id(user_id)
        return PremiumResponse(
            user_id=viewer_id,
            premium=user_has_premium_access(service, viewer_id),
            source=premium_source(service, viewer_id),
        )

    @app.post("/v1/premium/redeem", response_model=PremiumRedeemResponse)
    def redeem_premium(request: PremiumRedeemRequest) -> PremiumRedeemResponse:
        service: AppState = app.state.gitai
        viewer_id = sanitize_user_id(request.user_id)
        result = service.entitlements.redeem_premium_code(viewer_id, request.code)
        return PremiumRedeemResponse(
            user_id=viewer_id,
            premium=result.premium or user_has_premium_access(service, viewer_id),
            source=premium_source(service, viewer_id),
            code=result.code,
            status=result.status,
        )

    @app.post("/v1/pair-proposals", response_model=PairProposalResponse)
    def submit_pair_proposal(request: PairProposalRequest) -> PairProposalResponse:
        service: AppState = app.state.gitai
        enforce_rate_limit(
            service.submissions,
            request.user_id,
            "pair_proposal",
            PAIR_PROPOSAL_RATE_LIMIT,
        )
        try:
            result = SubmitPairProposalUseCase(
                object_catalog=service.object_catalog,
                proposals=service.pair_proposals,
            ).execute(
                SubmitPairProposalCommand(
                    user_id=request.user_id,
                    base_label=request.base_label,
                    target_label=request.target_label,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return pair_proposal_payload(
            proposal=result.proposal,
            service=service,
            base=result.base,
            target=result.target,
            hard_negatives=list(result.hard_negatives),
        )

    @app.get("/v1/pair-proposals", response_model=PairProposalsResponse)
    def pair_proposals(
        status: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> PairProposalsResponse:
        service: AppState = app.state.gitai
        status_value = parse_pair_proposal_status(status)
        return PairProposalsResponse(
            entries=[
                pair_proposal_payload(proposal, service=service)
                for proposal in service.pair_proposals.list(limit=limit, status=status_value)
            ]
        )

    @app.post("/v1/pair-proposals/{proposal_id}/review", response_model=PairProposalResponse)
    def review_pair_proposal(
        proposal_id: str,
        request: PairProposalReviewRequest,
    ) -> PairProposalResponse:
        service: AppState = app.state.gitai
        try:
            decision = parse_pair_proposal_review_decision(request.status)
            result = ReviewPairProposalUseCase(proposals=service.pair_proposals).execute(
                ReviewPairProposalCommand(
                    proposal_id=proposal_id,
                    reviewer_id=request.reviewer_id,
                    status=decision,
                    note=request.note,
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PairProposalReviewRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return pair_proposal_payload(result.proposal, service=service)

    @app.get("/v1/pair-seed-queue", response_model=PairSeedQueueResponse)
    def pair_seed_queue(
        limit: int = Query(default=50, ge=1, le=200),
    ) -> PairSeedQueueResponse:
        service: AppState = app.state.gitai
        result = BuildApprovedPairSeedQueueUseCase(
            object_catalog=service.object_catalog,
            proposals=service.pair_proposals,
        ).execute(BuildApprovedPairSeedQueueCommand(limit=limit))
        return PairSeedQueueResponse(
            entries=[pair_seed_queue_entry_payload(entry) for entry in result.entries],
            skipped=[
                PairSeedQueueSkippedResponse(
                    proposal_id=item.proposal_id,
                    pair_key=item.pair_key,
                    reason=item.reason,
                )
                for item in result.skipped
            ],
        )

    @app.get("/v1/share-card")
    def share_card(submission_id: str = Query()) -> Response:
        service: AppState = app.state.gitai
        try:
            submission = service.submissions.get(submission_id)
            pair = service.pairs.get(submission.pair_id)
            image_bytes = service.submission_images.read(submission.image_ref)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="submission image is not available") from exc
        if submission.ocr_cheat or submission.moderation != "pass":
            raise HTTPException(status_code=403, detail="submission is not shareable")
        comment = service.appraisals.get_cached_comment(submission.submission_id)
        card = build_share_card(
            submission=submission,
            pair=pair,
            image_bytes=image_bytes,
            comment=comment,
            season_label=season_label_for_response(service, submission.season_id),
            public_url=os.environ.get("GITAI_PUBLIC_WEB_URL", "").strip(),
        )
        return Response(
            content=card.png,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="{card.filename}"'},
        )

    mount_static_web_app(app)
    return app


def build_state_from_env() -> AppState:
    data_dir = Path(os.environ.get("GITAI_DATA_DIR", "data/scoring"))
    puzzle_dir = Path(os.environ.get("GITAI_PUZZLE_DIR", "data/puzzle"))
    pairs_path = Path(os.environ.get("GITAI_PAIRS_PATH", data_dir / "pairs.json"))
    seed_scores_path = Path(os.environ.get("GITAI_SEED_SCORES_PATH", data_dir / "seed_scores.json"))
    daily_puzzles_path = Path(os.environ.get("GITAI_DAILY_PUZZLES_PATH", puzzle_dir / "daily_puzzles.json"))
    object_catalog_path = Path(os.environ.get("GITAI_OBJECT_CATALOG_PATH", puzzle_dir / "object_catalog.json"))
    model = os.environ.get("GITAI_MODEL", "heuristic")
    ocr_kind = os.environ.get("GITAI_OCR", "fingerprint")
    moderation_kind = os.environ.get("GITAI_MODERATION", "fingerprint")

    class Args:
        pass

    args = Args()
    args.model = model
    args.device = os.environ.get("GITAI_DEVICE", "cpu")
    args.open_clip_model = os.environ.get("GITAI_OPEN_CLIP_MODEL", "ViT-L-14")
    args.open_clip_pretrained = os.environ.get("GITAI_OPEN_CLIP_PRETRAINED", "openai")
    args.siglip_model_id = os.environ.get("GITAI_SIGLIP_MODEL_ID", "google/siglip-base-patch16-224")

    if ocr_kind == "fingerprint":
        ocr = ImageFingerprintOcrScanner(data_dir / "ocr_fixtures.json")
    elif ocr_kind == "tesseract":
        ocr = TesseractOcrScanner()
    elif ocr_kind == "none":
        ocr = NullOcrScanner()
    else:
        raise ValueError(f"Unknown GITAI_OCR: {ocr_kind}")

    if moderation_kind == "fingerprint":
        moderator = ImageFingerprintModerator(data_dir / "moderation_fixtures.json")
    elif moderation_kind == "none":
        moderator = NullImageModerator()
    else:
        raise ValueError(f"Unknown GITAI_MODERATION: {moderation_kind}")

    runtime_db = Path(os.environ.get("GITAI_RUNTIME_DB", "data/runtime/gitai.sqlite"))
    submissions = SqliteSubmissionRepository(runtime_db)
    appraisals = SqliteAppraisalRepository(runtime_db)
    cosmetics = SqliteCosmeticRepository(runtime_db)
    entitlements = SqliteEntitlementRepository(runtime_db)
    pair_proposals = SqlitePairProposalRepository(runtime_db)
    seed_premium_redeem_codes(
        entitlements,
        os.environ.get("GITAI_PREMIUM_REDEEM_CODES", ""),
    )
    submission_images = LocalSubmissionImageStore(Path(os.environ.get("GITAI_IMAGE_STORE", "data/runtime/submissions")))
    seed_ghosts = JsonSeedGhostRepository(Path(os.environ.get("GITAI_SEED_GHOSTS", "data/competition/seed_ghosts.json"))).all()
    submissions.seed(seed_ghosts)
    judge = build_judge(args)
    season = build_season_from_env(judge.model_version)

    return AppState(
        pairs=PairRepository(pairs_path),
        seed_scores=SeedScoreRepository(seed_scores_path),
        daily_puzzles=DailyPuzzleRepository(daily_puzzles_path),
        object_catalog=ObjectCatalogRepository(object_catalog_path),
        pair_proposals=pair_proposals,
        submissions=submissions,
        submission_images=submission_images,
        appraisals=appraisals,
        cosmetics=cosmetics,
        entitlements=entitlements,
        appraisal_actor=build_layer2_actor_from_env(),
        daily_llm_spend_cap=int(os.environ.get("GITAI_DAILY_LLM_SPEND_CAP", "100")),
        user_daily_comment_limit=int(os.environ.get("GITAI_USER_DAILY_COMMENT_LIMIT", "3")),
        daily_submission_limit=int(os.environ.get("GITAI_DAILY_SUBMISSION_LIMIT", "10")),
        premium_user_ids=parse_premium_user_ids(os.environ.get("GITAI_PREMIUM_USER_IDS", "")),
        season=season,
        drawing_verifier=CanvasStrokeReplayVerifier(
            max_mean_abs_error=float(os.environ.get("GITAI_REPLAY_MAX_ERROR", "0.08")),
        ),
        judge=judge,
        ocr=ocr,
        moderator=moderator,
    )


def mount_static_web_app(app: FastAPI) -> None:
    static_dir = os.environ.get("GITAI_STATIC_DIR", "").strip()
    if not static_dir:
        return
    static_path = Path(static_dir)
    index_path = static_path / "index.html"
    if not static_path.is_dir() or not index_path.exists():
        raise RuntimeError(f"GITAI_STATIC_DIR must point to a built web dist with index.html: {static_path}")
    app.mount("/", StaticFiles(directory=static_path, html=True), name="web")


def cache_control_for_path(path: str) -> str:
    if path == "/healthz" or path.startswith("/v1/"):
        return "no-store"
    if path == "/" or path.endswith(".html"):
        return "no-cache"
    if path.startswith("/assets/"):
        return "public, max-age=31536000, immutable"
    if path.startswith("/brand/"):
        return "public, max-age=86400"
    if path in {"/site.webmanifest", "/robots.txt"}:
        return "public, max-age=3600"
    return ""


def object_label_payload(label) -> dict[str, Any]:
    return {
        "object_id": label.object_id,
        "canonical_label": label.canonical_label,
        "aliases": list(label.aliases),
    }


def catalog_object_payload(item: CatalogObject | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "object_id": item.object_id,
        "canonical_label": item.canonical_label,
        "aliases": list(item.aliases),
        "category": item.category,
    }


def pair_proposal_payload(
    proposal,
    service: AppState,
    base: CatalogObject | None = None,
    target: CatalogObject | None = None,
    hard_negatives: list[CatalogObject] | None = None,
) -> PairProposalResponse:
    if base is None and proposal.base_object_id:
        try:
            base = service.object_catalog.get(proposal.base_object_id)
        except KeyError:
            base = None
    if target is None and proposal.target_object_id:
        try:
            target = service.object_catalog.get(proposal.target_object_id)
        except KeyError:
            target = None
    if hard_negatives is None:
        hard_negatives = []
        for object_id in proposal.hard_negative_ids:
            try:
                hard_negatives.append(service.object_catalog.get(object_id))
            except KeyError:
                continue
    return PairProposalResponse(
        proposal_id=proposal.proposal_id,
        pair_key=proposal.pair_key,
        user_id=proposal.user_id,
        base_label=proposal.base_label,
        target_label=proposal.target_label,
        base=catalog_object_payload(base),
        target=catalog_object_payload(target),
        status=proposal.status,
        rejection_reasons=list(proposal.rejection_reasons),
        difficulty_prior=proposal.difficulty_prior,
        hard_negatives=[
            payload for payload in (catalog_object_payload(item) for item in hard_negatives) if payload is not None
        ],
        support_count=proposal.support_count,
        created_at=proposal.created_at.isoformat(),
        last_supported_at=proposal.last_supported_at.isoformat(),
        reviewer_id=proposal.reviewer_id,
        review_note=proposal.review_note,
        reviewed_at=proposal.reviewed_at.isoformat() if proposal.reviewed_at else None,
    )


def pair_seed_queue_entry_payload(entry) -> PairSeedQueueEntryResponse:
    return PairSeedQueueEntryResponse(
        proposal_id=entry.proposal_id,
        pair_key=entry.pair_key,
        pair_id=entry.pair_id,
        base=catalog_object_payload(entry.base) or {},
        target=catalog_object_payload(entry.target) or {},
        hard_negatives=[
            payload for payload in (catalog_object_payload(item) for item in entry.hard_negatives) if payload is not None
        ],
        difficulty_prior=entry.difficulty_prior,
        support_count=entry.support_count,
        reviewer_id=entry.reviewer_id,
        review_note=entry.review_note,
        reviewed_at=entry.reviewed_at.isoformat() if entry.reviewed_at else None,
        status=entry.status,
    )


def comment_payload(comment: AppraisalComment) -> AppraisalCommentResponse:
    return AppraisalCommentResponse(
        line=comment.line,
        mood=comment.mood,
        source=comment.source,
        template_id=comment.template_id,
    )


def cosmetic_payload(unlock: CosmeticUnlock) -> CosmeticResponse:
    return CosmeticResponse(
        cosmetic_id=unlock.cosmetic.cosmetic_id,
        kind=unlock.cosmetic.kind,
        label=unlock.cosmetic.label,
        colors=list(unlock.cosmetic.colors),
        newly_unlocked=unlock.newly_unlocked,
    )


def dedupe_cosmetic_unlocks(unlocks: list[CosmeticUnlock]) -> list[CosmeticUnlock]:
    seen: set[str] = set()
    deduped: list[CosmeticUnlock] = []
    for unlock in unlocks:
        if unlock.cosmetic.cosmetic_id in seen:
            continue
        seen.add(unlock.cosmetic.cosmetic_id)
        deduped.append(unlock)
    return deduped


def parse_leaderboard_kind(value: str) -> LeaderboardKind:
    if value == "score" or value == "efficiency" or value == "friend" or value == "funny":
        return value
    raise HTTPException(status_code=400, detail="kind must be score, efficiency, friend, or funny")


def parse_pair_proposal_status(value: str | None) -> PairProposalStatus | None:
    if value is None or value == "":
        return None
    if value in {"candidate", "needs_catalog_review", "approved", "rejected"}:
        return value
    raise HTTPException(
        status_code=400,
        detail="status must be candidate, needs_catalog_review, approved, or rejected",
    )


def parse_pair_proposal_review_decision(value: str) -> PairProposalReviewDecision:
    if value in {"approved", "needs_catalog_review", "rejected"}:
        return value
    raise HTTPException(
        status_code=400,
        detail="status must be approved, needs_catalog_review, or rejected",
    )


def require_friend_code_for_kind(kind: LeaderboardKind, value: str) -> str:
    friend_code = normalize_friend_code(value)
    if kind == "friend" and not friend_code:
        raise HTTPException(status_code=400, detail="friend_code is required for friend leaderboard")
    return friend_code


def build_season_from_env(active_model_version: str) -> SeasonSpec:
    season_id = normalize_season_id(os.environ.get("GITAI_SEASON_ID", "season-1")) or "season-1"
    season = SeasonSpec(
        season_id=season_id,
        label=os.environ.get("GITAI_SEASON_LABEL", "Season 1"),
        model_version=os.environ.get("GITAI_SEASON_MODEL_VERSION", active_model_version),
    )
    if season.model_version != active_model_version:
        raise ValueError(
            f"Season {season.season_id} pins {season.model_version}, "
            f"but active judge is {active_model_version}"
        )
    return season


def parse_season_id_query(service: AppState, value: str | None) -> str:
    if not value:
        return service.season.season_id
    return normalize_season_id(value) or service.season.season_id


def season_label_for_response(service: AppState, season_id: str) -> str:
    if season_id == service.season.season_id:
        return service.season.label
    return season_id


def puzzle_for_query(service: AppState, value: str | None):
    today = runtime_today()
    if not value:
        return service.daily_puzzles.current(today)
    puzzle_date = date.fromisoformat(value)
    if puzzle_date > today:
        raise KeyError(f"Daily puzzle is not available yet: {puzzle_date.isoformat()}")
    return service.daily_puzzles.get(puzzle_date)


def select_daily_ref(service: AppState, puzzle, allow_env_override: bool):
    override = os.environ.get("GITAI_DAILY_REF_VERSION", "") if allow_env_override else ""
    if override:
        return service.seed_scores.get(override)
    frozen_ref = service.seed_scores.get(puzzle.ref_version)
    if frozen_ref.model_version == service.judge.model_version:
        return frozen_ref
    compatible = service.seed_scores.find_compatible(
        pair_id=puzzle.pair_id,
        model_version=service.judge.model_version,
    )
    if compatible is None:
        raise KeyError(
            f"No seed score ref for pair_id={puzzle.pair_id} and model_version={service.judge.model_version}"
        )
    return compatible


def runtime_today() -> date:
    configured = os.environ.get("GITAI_TODAY", "")
    if configured:
        return date.fromisoformat(configured)
    return date.today()


def parse_premium_user_ids(value: str) -> set[str]:
    return {sanitize_user_id(item) for item in value.split(",") if item.strip()}


def seed_premium_redeem_codes(repository: SqliteEntitlementRepository, value: str) -> None:
    for item in value.split(","):
        raw = item.strip()
        if not raw:
            continue
        code, _, limit_text = raw.partition(":")
        limit = int(limit_text) if limit_text.strip().isdigit() else 100
        repository.seed_redeem_code(code, max_redemptions=limit)


def user_has_premium_access(service: AppState, user_id: str) -> bool:
    return user_id in service.premium_user_ids or service.entitlements.has_premium_access(user_id)


def premium_source(service: AppState, user_id: str) -> str:
    if user_id in service.premium_user_ids:
        return "static"
    entitlement = service.entitlements.active_entitlement(user_id)
    if entitlement is None:
        return "none"
    return entitlement.source


def enforce_rate_limit(
    submissions: SqliteSubmissionRepository,
    actor_id: str,
    action: str,
    rule: tuple[int, int],
) -> None:
    limit, window_seconds = rule
    decision = submissions.consume_rate_limit(
        actor_id=sanitize_user_id(actor_id),
        action=action,
        limit=limit,
        window_seconds=window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
