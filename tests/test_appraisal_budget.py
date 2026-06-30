from __future__ import annotations

from datetime import date, datetime, timezone
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


def test_layer2_comment_is_cached_and_charged_once(tmp_path: Path) -> None:
    submissions, images, appraisals = stores(tmp_path)
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")
    image_ref = images.save("one", Image.new("RGBA", (32, 32), "white"))
    submissions.save(record("one", image_ref=image_ref))
    usecase = MintAppraisalCommentUseCase(
        pairs=PairRepository(Path("data/scoring/pairs.json")),
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=ScriptedActor("これは由緒あるbaseballです。"),
        daily_cap_units=10,
        user_daily_limit=3,
    )

    first = usecase.execute(MintAppraisalCommentCommand("one", "viewer", day=date(2026, 6, 29)))
    second = usecase.execute(MintAppraisalCommentCommand("one", "viewer", day=date(2026, 6, 29)))

    assert first.status == "minted"
    assert first.comment.source == "layer2"
    assert first.daily_spend == 1
    assert second.status == "cached"
    assert second.comment == first.comment
    assert second.daily_spend == 1


def test_daily_budget_falls_back_to_template(tmp_path: Path) -> None:
    submissions, images, appraisals = stores(tmp_path)
    image_ref_a = images.save("a", Image.new("RGBA", (32, 32), "white"))
    image_ref_b = images.save("b", Image.new("RGBA", (32, 32), "white"))
    submissions.save(record("a", image_ref=image_ref_a))
    submissions.save(record("b", image_ref=image_ref_b))
    usecase = MintAppraisalCommentUseCase(
        pairs=PairRepository(Path("data/scoring/pairs.json")),
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=ScriptedActor("これは由緒あるbaseballです。"),
        daily_cap_units=1,
        user_daily_limit=3,
    )

    first = usecase.execute(MintAppraisalCommentCommand("a", "viewer", day=date(2026, 6, 29)))
    second = usecase.execute(MintAppraisalCommentCommand("b", "viewer", day=date(2026, 6, 29)))

    assert first.status == "minted"
    assert second.status == "fallback_budget"
    assert second.comment.source == "template_bank"
    assert second.daily_spend == 1


def test_unsafe_layer2_output_falls_back_but_records_spend(tmp_path: Path) -> None:
    submissions, images, appraisals = stores(tmp_path)
    image_ref = images.save("unsafe", Image.new("RGBA", (32, 32), "white"))
    submissions.save(record("unsafe", image_ref=image_ref))
    usecase = MintAppraisalCommentUseCase(
        pairs=PairRepository(Path("data/scoring/pairs.json")),
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=ScriptedActor("あなたはバカです。"),
        daily_cap_units=10,
        user_daily_limit=3,
    )

    result = usecase.execute(MintAppraisalCommentCommand("unsafe", "viewer", day=date(2026, 6, 29)))

    assert result.status == "fallback_output_filter"
    assert result.comment.source == "template_bank"
    assert result.daily_spend == 1
    assert appraisals.get_cached_comment("unsafe") is None


def test_hero_mode_can_mint_without_user_quota(tmp_path: Path) -> None:
    submissions, images, appraisals = stores(tmp_path)
    image_ref = images.save("hero", Image.new("RGBA", (32, 32), "white"))
    submissions.save(record("hero", image_ref=image_ref, percentile=0.99))
    usecase = MintAppraisalCommentUseCase(
        pairs=PairRepository(Path("data/scoring/pairs.json")),
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=ScriptedActor("これは由緒あるbaseballです。"),
        daily_cap_units=10,
        user_daily_limit=0,
    )

    result = usecase.execute(MintAppraisalCommentCommand("hero", "viewer", mode="hero", day=date(2026, 6, 29)))

    assert result.status == "minted"
    assert result.comment.source == "layer2"
    assert result.user_remaining == 0
    assert appraisals.user_daily_count("viewer", date(2026, 6, 29)) == 0
    assert result.daily_spend == 1


def test_hero_mode_requires_high_safe_submission(tmp_path: Path) -> None:
    submissions, images, appraisals = stores(tmp_path)
    image_ref = images.save("ordinary", Image.new("RGBA", (32, 32), "white"))
    submissions.save(record("ordinary", image_ref=image_ref, percentile=0.94))
    usecase = MintAppraisalCommentUseCase(
        pairs=PairRepository(Path("data/scoring/pairs.json")),
        submissions=submissions,
        submission_images=images,
        appraisals=appraisals,
        actor=ScriptedActor("これは由緒あるbaseballです。"),
        daily_cap_units=10,
        user_daily_limit=3,
    )

    result = usecase.execute(MintAppraisalCommentCommand("ordinary", "viewer", mode="hero", day=date(2026, 6, 29)))

    assert result.status == "fallback_hero_gate"
    assert result.comment.source == "template_bank"
    assert result.daily_spend == 0


def stores(tmp_path: Path):
    db_path = tmp_path / "appraisals.sqlite"
    return SqliteSubmissionRepository(db_path), MemorySubmissionImageStore(), SqliteAppraisalRepository(db_path)


def record(submission_id: str, image_ref: str, percentile: float = 1.0) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=submission_id,
        puzzle_date=date(2026, 6, 29),
        pair_id="apple_to_baseball",
        ref_version="phase0-heuristic-tau30-2026-06-29",
        player=PlayerIdentity(user_id=f"artist-{submission_id}", display_name=f"artist-{submission_id}"),
        image_hash=submission_id,
        image_ref=image_ref,
        stroke_count=1,
        score=round(1000 * percentile),
        percentile=percentile,
        raw=1.0,
        bucket="fooled",
        ocr_cheat=False,
        moderation="pass",
        model_version="heuristic-color-shape-v1",
        created_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )


class ScriptedActor:
    actor_version = "scripted-layer2-v1"
    estimated_cost_units = 1

    def __init__(self, line: str) -> None:
        self._line = line

    def generate(
        self,
        submission: SubmissionRecord,
        pair: PairSpec,
        image_bytes: bytes,
    ) -> GeneratedAppraisalComment:
        return GeneratedAppraisalComment(
            comment=AppraisalComment(
                line=self._line,
                mood="smug",
                source="layer2",
                template_id="scripted-layer2",
            ),
            cost_units=1,
            actor_version=self.actor_version,
        )
