from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path

from PIL import Image

from gitai_phase0.application import MintAppraisalCommentCommand, MintAppraisalCommentUseCase
from gitai_phase0.commentary import AppraisalComment, GeneratedAppraisalComment
from gitai_phase0.commentary_repositories import SqliteAppraisalRepository
from gitai_phase0.competition import PlayerIdentity, SubmissionRecord
from gitai_phase0.competition_repositories import SqliteSubmissionRepository
from gitai_phase0.domain import PairSpec
from gitai_phase0.repositories import PairRepository
from gitai_phase0.submission_images import MemorySubmissionImageStore


@dataclass(frozen=True)
class BudgetSmokeStatus:
    status: str
    count: int


@dataclass(frozen=True)
class AppraisalBudgetSmokeReport:
    generated_at: str
    request_count: int
    mode: str
    daily_cap_units: int
    user_daily_limit: int
    actor_cost_units: int
    daily_spend: int
    gate_passed: bool
    degraded_gracefully: bool
    status_counts: tuple[BudgetSmokeStatus, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def run_appraisal_budget_smoke(
    runtime_db: Path,
    pairs_path: Path,
    request_count: int = 25,
    daily_cap_units: int = 5,
    user_daily_limit: int = 25,
    mode: str = "hero",
    day: date = date(2026, 6, 29),
) -> AppraisalBudgetSmokeReport:
    submissions = SqliteSubmissionRepository(runtime_db)
    appraisals = SqliteAppraisalRepository(runtime_db)
    images = MemorySubmissionImageStore()
    pairs = PairRepository(pairs_path)
    pair = first_pair(pairs)
    actor = ScriptedBudgetActor()
    usecase = MintAppraisalCommentUseCase(
        pairs=pairs,
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=actor,
        daily_cap_units=daily_cap_units,
        user_daily_limit=user_daily_limit,
    )

    statuses: list[str] = []
    for index in range(request_count):
        submission_id = f"budget-smoke-{index:04d}"
        image_ref = images.save(submission_id, Image.new("RGBA", (32, 32), "white"))
        submissions.save(
            _record(submission_id, image_ref=image_ref, user_id=f"artist-{index:04d}", pair_id=pair.pair_id)
        )
        result = usecase.execute(
            MintAppraisalCommentCommand(
                submission_id=submission_id,
                user_id=f"viewer-{index:04d}",
                mode=mode,
                day=day,
            )
        )
        statuses.append(result.status)

    counter = Counter(statuses)
    daily_spend = appraisals.daily_spend(day)
    degraded_gracefully = counter.get("fallback_budget", 0) > 0
    gate_passed = daily_spend <= daily_cap_units and degraded_gracefully
    return AppraisalBudgetSmokeReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        request_count=request_count,
        mode=mode,
        daily_cap_units=daily_cap_units,
        user_daily_limit=user_daily_limit,
        actor_cost_units=actor.estimated_cost_units,
        daily_spend=daily_spend,
        gate_passed=gate_passed,
        degraded_gracefully=degraded_gracefully,
        status_counts=tuple(BudgetSmokeStatus(status=status, count=count) for status, count in sorted(counter.items())),
    )


def first_pair(pairs: PairRepository) -> PairSpec:
    pair_list = pairs.list()
    if not pair_list:
        raise ValueError("budget smoke requires at least one pair")
    return pair_list[0]


def render_appraisal_budget_smoke_markdown(report: AppraisalBudgetSmokeReport) -> str:
    lines = [
        "# Phase 5 Layer2 budget smoke",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- request_count: `{report.request_count}`",
        f"- mode: `{report.mode}`",
        f"- daily_cap_units: `{report.daily_cap_units}`",
        f"- daily_spend: `{report.daily_spend}`",
        f"- gate_passed: `{'true' if report.gate_passed else 'false'}`",
        f"- degraded_gracefully: `{'true' if report.degraded_gracefully else 'false'}`",
        "",
        "| status | count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{item.status}` | {item.count} |" for item in report.status_counts)
    return "\n".join(lines) + "\n"


def write_appraisal_budget_smoke_report(
    report: AppraisalBudgetSmokeReport,
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "phase5_budget_smoke.json"
    markdown_path = out_dir / "phase5_budget_smoke.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_appraisal_budget_smoke_markdown(report), encoding="utf-8")
    return json_path, markdown_path


class ScriptedBudgetActor:
    actor_version = "scripted-budget-smoke-v1"
    estimated_cost_units = 1

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment:
        return GeneratedAppraisalComment(
            comment=AppraisalComment(
                line="The appraiser confidently accepts the disguise.",
                mood="smug",
                source="layer2",
                template_id="scripted-budget-smoke",
            ),
            cost_units=self.estimated_cost_units,
            actor_version=self.actor_version,
        )


def _record(
    submission_id: str,
    image_ref: str,
    user_id: str,
    pair_id: str = "apple_to_baseball",
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=submission_id,
        puzzle_date=date(2026, 6, 29),
        pair_id=pair_id,
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity(user_id=user_id, display_name=user_id),
        image_hash=submission_id,
        image_ref=image_ref,
        stroke_count=2,
        score=990,
        percentile=0.99,
        raw=0.99,
        bucket="fooled",
        ocr_cheat=False,
        moderation="pass",
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )
