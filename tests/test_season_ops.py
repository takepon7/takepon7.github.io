from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from gitai_phase0.commentary_repositories import SqliteAppraisalRepository
from gitai_phase0.competition import PlayerIdentity, SubmissionRecord
from gitai_phase0.competition_repositories import SqliteSubmissionRepository
from gitai_phase0.cosmetic_repositories import SqliteCosmeticRepository
from gitai_phase0.cosmetics import COSMETIC_CATALOG
from gitai_phase0.entitlement_repositories import SqliteEntitlementRepository
from gitai_phase0.season_ops import build_season_ops_report, render_season_ops_markdown


def test_season_ops_report_summarizes_safety_spend_and_rewards(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    submissions = SqliteSubmissionRepository(db_path)
    appraisals = SqliteAppraisalRepository(db_path)
    cosmetics = SqliteCosmeticRepository(db_path)
    entitlements = SqliteEntitlementRepository(db_path)

    submissions.save(record("public-top", score=960, user_id="artist-a"))
    submissions.save(record("text-cheat", score=1000, ocr_cheat=True, user_id="artist-b"))
    submissions.save(record("flagged", score=900, moderation="flag", user_id="artist-c"))
    submissions.save(record("old-model", score=700, model_version="heuristic-previous-v0", user_id="artist-d"))
    submissions.save(record("other-season", season_id="season-2", score=1000, user_id="artist-e"))
    submissions.record_content_report("report-1", "flagged", "viewer-a", "unsafe", "review")
    submissions.record_content_report("report-2", "old-model", "viewer-b", "spam", "")
    submissions.record_playtest_feedback("feedback-1", "public-top", "viewer-a", "fun", "")
    submissions.record_playtest_feedback("feedback-2", "old-model", "viewer-b", "bug", "felt stuck")
    submissions.record_playtest_feedback("feedback-other", "other-season", "viewer-z", "hard", "")
    appraisals.record_spend(
        "public-top",
        "artist-a",
        actor_version="scripted-layer2-v1",
        cost_units=2,
        day=date(2026, 6, 29),
    )
    appraisals.record_spend(
        "other-season",
        "artist-e",
        actor_version="scripted-layer2-v1",
        cost_units=99,
        day=date(2026, 6, 29),
    )
    rewards = tuple(spec for spec in COSMETIC_CATALOG if spec.score_floor > 0)
    cosmetics.unlock_cosmetics("artist-a", "season-1", rewards)
    cosmetics.unlock_cosmetics("artist-e", "season-2", rewards)
    entitlements.seed_redeem_code("founder-pass", max_redemptions=10)
    entitlements.redeem_premium_code("artist-a", "founder-pass")

    report = build_season_ops_report(
        runtime_db=db_path,
        season_id="season-1",
        season_label="Season 1",
        pinned_model_version="heuristic-color-shape-v1",
    )

    assert report.missing_tables == ()
    assert report.model_pin_ok is False
    assert report.submission_summary.total == 4
    assert report.submission_summary.public_rankable == 2
    assert report.submission_summary.hidden_from_public == 2
    assert report.submission_summary.ocr_cheat == 1
    assert report.submission_summary.moderation_flagged == 1
    assert report.spend_summary.event_count == 1
    assert report.spend_summary.total_cost_units == 2
    assert [item.name for item in report.cosmetic_summary.by_cosmetic_id] == [
        "palette-masterpiece",
        "palette-verdict",
    ]
    assert report.premium_summary.active_entitlements == 1
    assert report.premium_summary.redeem_codes == 1
    assert report.premium_summary.redemptions == 1
    assert report.feedback_summary.content_reports == 2
    assert report.feedback_summary.playtest_feedback == 2
    assert report.feedback_summary.playtest_distinct_users == 2
    assert [item.name for item in report.feedback_summary.by_report_reason] == ["spam", "unsafe"]
    assert [item.name for item in report.feedback_summary.by_playtest_sentiment] == ["bug", "fun"]
    assert sum(item.count for item in report.ref_versions if item.needs_rescore) == 1


def test_season_ops_markdown_flags_model_pin_failures(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    submissions = SqliteSubmissionRepository(db_path)
    SqliteAppraisalRepository(db_path)
    SqliteCosmeticRepository(db_path)
    SqliteEntitlementRepository(db_path)
    submissions.save(record("old-model", model_version="heuristic-previous-v0"))

    report = build_season_ops_report(
        runtime_db=db_path,
        season_id="season-1",
        season_label="Season 1",
        pinned_model_version="heuristic-color-shape-v1",
    )
    markdown = render_season_ops_markdown(report)

    assert "model_pin_ok: `false`" in markdown
    assert "| `heuristic-previous-v0` | 1 | no |" in markdown
    assert "rescore_candidate_submissions: `1`" in markdown
    assert "## Feedback" in markdown


def test_season_ops_report_handles_missing_database(tmp_path: Path) -> None:
    report = build_season_ops_report(
        runtime_db=tmp_path / "missing.sqlite",
        season_id="season-1",
        season_label="Season 1",
        pinned_model_version="heuristic-color-shape-v1",
    )

    assert report.model_pin_ok is True
    assert report.submission_summary.total == 0
    assert "database" in report.missing_tables


def record(
    submission_id: str,
    season_id: str = "season-1",
    score: int = 900,
    model_version: str = "heuristic-color-shape-v1",
    ocr_cheat: bool = False,
    moderation: str = "pass",
    user_id: str = "artist",
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=submission_id,
        season_id=season_id,
        puzzle_date=date(2026, 6, 29),
        pair_id="apple_to_baseball",
        ref_version=f"phase0-{model_version}-tau30-2026-06-29",
        player=PlayerIdentity(user_id=user_id, display_name=user_id),
        image_hash=submission_id,
        image_ref=f"memory:{submission_id}",
        stroke_count=3,
        score=score,
        percentile=score / 1000,
        raw=score / 1000,
        bucket="fooled",
        ocr_cheat=ocr_cheat,
        moderation=moderation,
        model_version=model_version,
        created_at=datetime(2026, 6, 29, 0, 0, tzinfo=timezone.utc),
    )
