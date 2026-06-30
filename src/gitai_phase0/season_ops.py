from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from gitai_phase0.competition import DEFAULT_SEASON_ID, normalize_season_id


@dataclass(frozen=True)
class SubmissionOpsSummary:
    total: int
    public_rankable: int
    hidden_from_public: int
    ocr_cheat: int
    moderation_flagged: int
    distinct_users: int
    puzzle_days: int
    first_submission_at: str | None
    last_submission_at: str | None
    score_min: int | None
    score_max: int | None
    score_avg: float | None
    percentile_avg: float | None


@dataclass(frozen=True)
class ModelVersionSummary:
    model_version: str
    count: int
    pinned: bool


@dataclass(frozen=True)
class RefVersionSummary:
    ref_version: str
    model_version: str
    count: int
    needs_rescore: bool


@dataclass(frozen=True)
class CostSummary:
    name: str
    count: int
    cost_units: int


@dataclass(frozen=True)
class SpendOpsSummary:
    event_count: int
    total_cost_units: int
    distinct_users: int
    by_actor_version: tuple[CostSummary, ...]


@dataclass(frozen=True)
class CountSummary:
    name: str
    count: int


@dataclass(frozen=True)
class CosmeticOpsSummary:
    unlock_count: int
    distinct_users: int
    by_cosmetic_id: tuple[CountSummary, ...]


@dataclass(frozen=True)
class PremiumOpsSummary:
    active_entitlements: int
    redeem_codes: int
    redemptions: int
    by_source: tuple[CountSummary, ...]


@dataclass(frozen=True)
class FeedbackOpsSummary:
    content_reports: int
    playtest_feedback: int
    playtest_distinct_users: int
    by_report_reason: tuple[CountSummary, ...]
    by_playtest_sentiment: tuple[CountSummary, ...]


@dataclass(frozen=True)
class SeasonOpsReport:
    season_id: str
    season_label: str
    pinned_model_version: str
    generated_at: str
    runtime_db: str
    missing_tables: tuple[str, ...]
    model_pin_ok: bool
    submission_summary: SubmissionOpsSummary
    model_versions: tuple[ModelVersionSummary, ...]
    ref_versions: tuple[RefVersionSummary, ...]
    spend_summary: SpendOpsSummary
    cosmetic_summary: CosmeticOpsSummary
    premium_summary: PremiumOpsSummary
    feedback_summary: FeedbackOpsSummary

    def to_dict(self) -> dict:
        return asdict(self)


def build_season_ops_report(
    runtime_db: Path,
    season_id: str,
    season_label: str,
    pinned_model_version: str,
) -> SeasonOpsReport:
    normalized_season_id = normalize_season_id(season_id) or DEFAULT_SEASON_ID
    generated_at = datetime.now(timezone.utc).isoformat()
    if not runtime_db.exists():
        return _empty_report(
            runtime_db=runtime_db,
            season_id=normalized_season_id,
            season_label=season_label,
            pinned_model_version=pinned_model_version,
            generated_at=generated_at,
            missing_tables=(
                "database",
                "submissions",
                "llm_spend_events",
                "cosmetic_unlocks",
                "premium_entitlements",
                "premium_redeem_codes",
                "premium_redemptions",
                "content_reports",
                "playtest_feedback",
            ),
        )

    with _connect_readonly(runtime_db) as conn:
        tables = _table_names(conn)
        missing_tables = tuple(
            name
            for name in (
                "submissions",
                "llm_spend_events",
                "cosmetic_unlocks",
                "premium_entitlements",
                "premium_redeem_codes",
                "premium_redemptions",
                "content_reports",
                "playtest_feedback",
            )
            if name not in tables
        )
        if "submissions" in tables:
            submission_summary = _submission_summary(conn, normalized_season_id)
            model_versions = _model_versions(conn, normalized_season_id, pinned_model_version)
            ref_versions = _ref_versions(conn, normalized_season_id, pinned_model_version)
        else:
            submission_summary = _empty_submission_summary()
            model_versions = ()
            ref_versions = ()

        spend_summary = (
            _spend_summary(conn, normalized_season_id)
            if {"submissions", "llm_spend_events"}.issubset(tables)
            else _empty_spend_summary()
        )
        cosmetic_summary = (
            _cosmetic_summary(conn, normalized_season_id)
            if "cosmetic_unlocks" in tables
            else _empty_cosmetic_summary()
        )
        premium_summary = (
            _premium_summary(conn)
            if {"premium_entitlements", "premium_redeem_codes", "premium_redemptions"}.issubset(tables)
            else _empty_premium_summary()
        )
        feedback_summary = (
            _feedback_summary(conn, normalized_season_id)
            if {"submissions", "content_reports", "playtest_feedback"}.issubset(tables)
            else _empty_feedback_summary()
        )

    return SeasonOpsReport(
        season_id=normalized_season_id,
        season_label=season_label,
        pinned_model_version=pinned_model_version,
        generated_at=generated_at,
        runtime_db=str(runtime_db),
        missing_tables=missing_tables,
        model_pin_ok=all(item.pinned for item in model_versions),
        submission_summary=submission_summary,
        model_versions=model_versions,
        ref_versions=ref_versions,
        spend_summary=spend_summary,
        cosmetic_summary=cosmetic_summary,
        premium_summary=premium_summary,
        feedback_summary=feedback_summary,
    )


def render_season_ops_markdown(report: SeasonOpsReport) -> str:
    rescore_count = sum(item.count for item in report.ref_versions if item.needs_rescore)
    lines = [
        f"# Season ops report: {report.season_label}",
        "",
        f"- season_id: `{report.season_id}`",
        f"- generated_at: `{report.generated_at}`",
        f"- runtime_db: `{report.runtime_db}`",
        f"- pinned_model_version: `{report.pinned_model_version}`",
        f"- model_pin_ok: `{'true' if report.model_pin_ok else 'false'}`",
        f"- rescore_candidate_submissions: `{rescore_count}`",
    ]
    if report.missing_tables:
        lines.append(f"- missing_tables: `{', '.join(report.missing_tables)}`")
    lines.extend(
        [
            "",
            "## Submissions",
            "",
            "| metric | value |",
            "| --- | ---: |",
            f"| total | {report.submission_summary.total} |",
            f"| public_rankable | {report.submission_summary.public_rankable} |",
            f"| hidden_from_public | {report.submission_summary.hidden_from_public} |",
            f"| ocr_cheat | {report.submission_summary.ocr_cheat} |",
            f"| moderation_flagged | {report.submission_summary.moderation_flagged} |",
            f"| distinct_users | {report.submission_summary.distinct_users} |",
            f"| puzzle_days | {report.submission_summary.puzzle_days} |",
            f"| score_avg | {_format_float(report.submission_summary.score_avg)} |",
            f"| percentile_avg | {_format_float(report.submission_summary.percentile_avg)} |",
            "",
            "## Model Versions",
            "",
            "| model_version | count | pinned |",
            "| --- | ---: | --- |",
        ]
    )
    lines.extend(
        f"| `{item.model_version}` | {item.count} | {'yes' if item.pinned else 'no'} |"
        for item in report.model_versions
    )
    if not report.model_versions:
        lines.append("| n/a | 0 | yes |")
    lines.extend(
        [
            "",
            "## Ref Versions",
            "",
            "| ref_version | model_version | count | needs_rescore |",
            "| --- | --- | ---: | --- |",
        ]
    )
    lines.extend(
        f"| `{item.ref_version}` | `{item.model_version}` | {item.count} | {'yes' if item.needs_rescore else 'no'} |"
        for item in report.ref_versions
    )
    if not report.ref_versions:
        lines.append("| n/a | n/a | 0 | no |")
    lines.extend(
        [
            "",
            "## LLM Spend",
            "",
            f"- events: `{report.spend_summary.event_count}`",
            f"- total_cost_units: `{report.spend_summary.total_cost_units}`",
            f"- distinct_users: `{report.spend_summary.distinct_users}`",
            "",
            "| actor_version | events | cost_units |",
            "| --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.name}` | {item.count} | {item.cost_units} |"
        for item in report.spend_summary.by_actor_version
    )
    if not report.spend_summary.by_actor_version:
        lines.append("| n/a | 0 | 0 |")
    lines.extend(
        [
            "",
            "## Cosmetics",
            "",
            f"- unlocks: `{report.cosmetic_summary.unlock_count}`",
            f"- distinct_users: `{report.cosmetic_summary.distinct_users}`",
            "",
            "| cosmetic_id | unlocks |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.name}` | {item.count} |"
        for item in report.cosmetic_summary.by_cosmetic_id
    )
    if not report.cosmetic_summary.by_cosmetic_id:
        lines.append("| n/a | 0 |")
    lines.extend(
        [
            "",
            "## Premium",
            "",
            f"- active_entitlements: `{report.premium_summary.active_entitlements}`",
            f"- redeem_codes: `{report.premium_summary.redeem_codes}`",
            f"- redemptions: `{report.premium_summary.redemptions}`",
            "",
            "| source | active_entitlements |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.name}` | {item.count} |"
        for item in report.premium_summary.by_source
    )
    if not report.premium_summary.by_source:
        lines.append("| n/a | 0 |")
    lines.extend(
        [
            "",
            "## Feedback",
            "",
            f"- content_reports: `{report.feedback_summary.content_reports}`",
            f"- playtest_feedback: `{report.feedback_summary.playtest_feedback}`",
            f"- playtest_distinct_users: `{report.feedback_summary.playtest_distinct_users}`",
            "",
            "| report_reason | count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.name}` | {item.count} |"
        for item in report.feedback_summary.by_report_reason
    )
    if not report.feedback_summary.by_report_reason:
        lines.append("| n/a | 0 |")
    lines.extend(
        [
            "",
            "| playtest_sentiment | count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.name}` | {item.count} |"
        for item in report.feedback_summary.by_playtest_sentiment
    )
    if not report.feedback_summary.by_playtest_sentiment:
        lines.append("| n/a | 0 |")
    return "\n".join(lines) + "\n"


def write_season_ops_report(report: SeasonOpsReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"season_ops_{report.season_id}"
    json_path = out_dir / f"{stem}.json"
    markdown_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_season_ops_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("select name from sqlite_master where type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _submission_summary(conn: sqlite3.Connection, season_id: str) -> SubmissionOpsSummary:
    row = conn.execute(
        """
        select
          count(*) as total,
          coalesce(sum(case when ocr_cheat = 0 and moderation = 'pass' then 1 else 0 end), 0) as public_rankable,
          coalesce(sum(case when ocr_cheat != 0 then 1 else 0 end), 0) as ocr_cheat,
          coalesce(sum(case when moderation != 'pass' then 1 else 0 end), 0) as moderation_flagged,
          count(distinct user_id) as distinct_users,
          count(distinct puzzle_date) as puzzle_days,
          min(created_at) as first_submission_at,
          max(created_at) as last_submission_at,
          min(score) as score_min,
          max(score) as score_max,
          avg(score) as score_avg,
          avg(percentile) as percentile_avg
        from submissions
        where season_id = ?
        """,
        (season_id,),
    ).fetchone()
    total = _int(row, "total")
    public_rankable = _int(row, "public_rankable")
    return SubmissionOpsSummary(
        total=total,
        public_rankable=public_rankable,
        hidden_from_public=total - public_rankable,
        ocr_cheat=_int(row, "ocr_cheat"),
        moderation_flagged=_int(row, "moderation_flagged"),
        distinct_users=_int(row, "distinct_users"),
        puzzle_days=_int(row, "puzzle_days"),
        first_submission_at=_str_or_none(row, "first_submission_at"),
        last_submission_at=_str_or_none(row, "last_submission_at"),
        score_min=_int_or_none(row, "score_min"),
        score_max=_int_or_none(row, "score_max"),
        score_avg=_float_or_none(row, "score_avg"),
        percentile_avg=_float_or_none(row, "percentile_avg"),
    )


def _model_versions(
    conn: sqlite3.Connection,
    season_id: str,
    pinned_model_version: str,
) -> tuple[ModelVersionSummary, ...]:
    rows = conn.execute(
        """
        select model_version, count(*) as count
        from submissions
        where season_id = ?
        group by model_version
        order by count desc, model_version
        """,
        (season_id,),
    ).fetchall()
    return tuple(
        ModelVersionSummary(
            model_version=str(row["model_version"]),
            count=int(row["count"]),
            pinned=str(row["model_version"]) == pinned_model_version,
        )
        for row in rows
    )


def _ref_versions(
    conn: sqlite3.Connection,
    season_id: str,
    pinned_model_version: str,
) -> tuple[RefVersionSummary, ...]:
    rows = conn.execute(
        """
        select ref_version, model_version, count(*) as count
        from submissions
        where season_id = ?
        group by ref_version, model_version
        order by count desc, ref_version, model_version
        """,
        (season_id,),
    ).fetchall()
    return tuple(
        RefVersionSummary(
            ref_version=str(row["ref_version"]),
            model_version=str(row["model_version"]),
            count=int(row["count"]),
            needs_rescore=str(row["model_version"]) != pinned_model_version,
        )
        for row in rows
    )


def _spend_summary(conn: sqlite3.Connection, season_id: str) -> SpendOpsSummary:
    row = conn.execute(
        """
        select
          count(*) as event_count,
          coalesce(sum(e.cost_units), 0) as total_cost_units,
          count(distinct e.user_id) as distinct_users
        from llm_spend_events e
        join submissions s on s.submission_id = e.submission_id
        where s.season_id = ?
        """,
        (season_id,),
    ).fetchone()
    actor_rows = conn.execute(
        """
        select e.actor_version, count(*) as count, coalesce(sum(e.cost_units), 0) as cost_units
        from llm_spend_events e
        join submissions s on s.submission_id = e.submission_id
        where s.season_id = ?
        group by e.actor_version
        order by cost_units desc, count desc, e.actor_version
        """,
        (season_id,),
    ).fetchall()
    return SpendOpsSummary(
        event_count=_int(row, "event_count"),
        total_cost_units=_int(row, "total_cost_units"),
        distinct_users=_int(row, "distinct_users"),
        by_actor_version=tuple(
            CostSummary(
                name=str(item["actor_version"]),
                count=int(item["count"]),
                cost_units=int(item["cost_units"]),
            )
            for item in actor_rows
        ),
    )


def _cosmetic_summary(conn: sqlite3.Connection, season_id: str) -> CosmeticOpsSummary:
    row = conn.execute(
        """
        select count(*) as unlock_count, count(distinct user_id) as distinct_users
        from cosmetic_unlocks
        where season_id = ?
        """,
        (season_id,),
    ).fetchone()
    rows = conn.execute(
        """
        select cosmetic_id, count(*) as count
        from cosmetic_unlocks
        where season_id = ?
        group by cosmetic_id
        order by count desc, cosmetic_id
        """,
        (season_id,),
    ).fetchall()
    return CosmeticOpsSummary(
        unlock_count=_int(row, "unlock_count"),
        distinct_users=_int(row, "distinct_users"),
        by_cosmetic_id=tuple(CountSummary(name=str(item["cosmetic_id"]), count=int(item["count"])) for item in rows),
    )


def _premium_summary(conn: sqlite3.Connection) -> PremiumOpsSummary:
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        """
        select count(*) as active_entitlements
        from premium_entitlements
        where expires_at is null or expires_at > ?
        """,
        (now,),
    ).fetchone()
    code_row = conn.execute(
        "select count(*) as redeem_codes from premium_redeem_codes",
    ).fetchone()
    redemption_row = conn.execute(
        "select count(*) as redemptions from premium_redemptions",
    ).fetchone()
    source_rows = conn.execute(
        """
        select source, count(*) as count
        from premium_entitlements
        where expires_at is null or expires_at > ?
        group by source
        order by count desc, source
        """,
        (now,),
    ).fetchall()
    return PremiumOpsSummary(
        active_entitlements=_int(row, "active_entitlements"),
        redeem_codes=_int(code_row, "redeem_codes"),
        redemptions=_int(redemption_row, "redemptions"),
        by_source=tuple(CountSummary(name=str(item["source"]), count=int(item["count"])) for item in source_rows),
    )


def _feedback_summary(conn: sqlite3.Connection, season_id: str) -> FeedbackOpsSummary:
    report_row = conn.execute(
        """
        select count(*) as content_reports
        from content_reports cr
        join submissions s on s.submission_id = cr.submission_id
        where s.season_id = ?
        """,
        (season_id,),
    ).fetchone()
    report_reason_rows = conn.execute(
        """
        select cr.reason, count(*) as count
        from content_reports cr
        join submissions s on s.submission_id = cr.submission_id
        where s.season_id = ?
        group by cr.reason
        order by count desc, cr.reason
        """,
        (season_id,),
    ).fetchall()
    feedback_row = conn.execute(
        """
        select count(*) as playtest_feedback, count(distinct pf.user_id) as playtest_distinct_users
        from playtest_feedback pf
        join submissions s on s.submission_id = pf.submission_id
        where s.season_id = ?
        """,
        (season_id,),
    ).fetchone()
    sentiment_rows = conn.execute(
        """
        select pf.sentiment, count(*) as count
        from playtest_feedback pf
        join submissions s on s.submission_id = pf.submission_id
        where s.season_id = ?
        group by pf.sentiment
        order by count desc, pf.sentiment
        """,
        (season_id,),
    ).fetchall()
    return FeedbackOpsSummary(
        content_reports=_int(report_row, "content_reports"),
        playtest_feedback=_int(feedback_row, "playtest_feedback"),
        playtest_distinct_users=_int(feedback_row, "playtest_distinct_users"),
        by_report_reason=tuple(
            CountSummary(name=str(item["reason"]), count=int(item["count"])) for item in report_reason_rows
        ),
        by_playtest_sentiment=tuple(
            CountSummary(name=str(item["sentiment"]), count=int(item["count"])) for item in sentiment_rows
        ),
    )


def _empty_report(
    runtime_db: Path,
    season_id: str,
    season_label: str,
    pinned_model_version: str,
    generated_at: str,
    missing_tables: tuple[str, ...],
) -> SeasonOpsReport:
    return SeasonOpsReport(
        season_id=season_id,
        season_label=season_label,
        pinned_model_version=pinned_model_version,
        generated_at=generated_at,
        runtime_db=str(runtime_db),
        missing_tables=missing_tables,
        model_pin_ok=True,
        submission_summary=_empty_submission_summary(),
        model_versions=(),
        ref_versions=(),
        spend_summary=_empty_spend_summary(),
        cosmetic_summary=_empty_cosmetic_summary(),
        premium_summary=_empty_premium_summary(),
        feedback_summary=_empty_feedback_summary(),
    )


def _empty_submission_summary() -> SubmissionOpsSummary:
    return SubmissionOpsSummary(
        total=0,
        public_rankable=0,
        hidden_from_public=0,
        ocr_cheat=0,
        moderation_flagged=0,
        distinct_users=0,
        puzzle_days=0,
        first_submission_at=None,
        last_submission_at=None,
        score_min=None,
        score_max=None,
        score_avg=None,
        percentile_avg=None,
    )


def _empty_spend_summary() -> SpendOpsSummary:
    return SpendOpsSummary(event_count=0, total_cost_units=0, distinct_users=0, by_actor_version=())


def _empty_cosmetic_summary() -> CosmeticOpsSummary:
    return CosmeticOpsSummary(unlock_count=0, distinct_users=0, by_cosmetic_id=())


def _empty_premium_summary() -> PremiumOpsSummary:
    return PremiumOpsSummary(active_entitlements=0, redeem_codes=0, redemptions=0, by_source=())


def _empty_feedback_summary() -> FeedbackOpsSummary:
    return FeedbackOpsSummary(
        content_reports=0,
        playtest_feedback=0,
        playtest_distinct_users=0,
        by_report_reason=(),
        by_playtest_sentiment=(),
    )


def _int(row: sqlite3.Row, key: str) -> int:
    return int(row[key] or 0)


def _int_or_none(row: sqlite3.Row, key: str) -> int | None:
    value = row[key]
    return None if value is None else int(value)


def _float_or_none(row: sqlite3.Row, key: str) -> float | None:
    value = row[key]
    return None if value is None else float(value)


def _str_or_none(row: sqlite3.Row, key: str) -> str | None:
    value = row[key]
    return None if value is None else str(value)


def _format_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"
