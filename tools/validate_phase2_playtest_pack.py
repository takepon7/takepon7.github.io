from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from gitai_phase0.puzzle import CurationPolicy
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository, SeedScoreRepository

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DailyPackRow:
    date: str
    pair_id: str
    ref_version: str
    model_version: str
    spread: float
    p50: float
    accepted: bool


@dataclass(frozen=True)
class DailyPackReport:
    daily_count: int
    valid: bool
    rows: tuple[DailyPackRow, ...]
    errors: tuple[str, ...]


def main() -> None:
    report = build_report()
    out_dir = ROOT / "reports" / "phase2"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "playtest_pack.json"
    markdown_path = out_dir / "playtest_pack.md"
    json_path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    if not report.valid:
        raise SystemExit(1)


def build_report() -> DailyPackReport:
    pairs = PairRepository(ROOT / "data" / "scoring" / "pairs.json")
    refs = SeedScoreRepository(ROOT / "data" / "scoring" / "seed_scores.json")
    daily = DailyPuzzleRepository(ROOT / "data" / "puzzle" / "daily_puzzles.json")
    policy = CurationPolicy()
    rows: list[DailyPackRow] = []
    errors: list[str] = []
    for puzzle in daily.list():
        try:
            pair = pairs.get(puzzle.pair_id)
            ref = refs.get(puzzle.ref_version)
        except KeyError as exc:
            errors.append(f"{puzzle.date.isoformat()}: {exc}")
            continue
        quality = policy.evaluate_seed_scores(ref)
        if ref.pair_id != pair.pair_id:
            errors.append(f"{puzzle.date.isoformat()}: ref pair {ref.pair_id} does not match {pair.pair_id}")
        if not quality.accepted:
            errors.append(f"{puzzle.date.isoformat()}: seed distribution is rejected")
        rows.append(
            DailyPackRow(
                date=puzzle.date.isoformat(),
                pair_id=puzzle.pair_id,
                ref_version=puzzle.ref_version,
                model_version=ref.model_version,
                spread=quality.spread,
                p50=quality.p50,
                accepted=quality.accepted,
            )
        )
    return DailyPackReport(
        daily_count=len(rows),
        valid=not errors and len(rows) >= 7,
        rows=tuple(rows),
        errors=tuple(errors),
    )


def render_markdown(report: DailyPackReport) -> str:
    lines = [
        "# Phase 2 playtest pack",
        "",
        f"- daily_count: `{report.daily_count}`",
        f"- valid: `{'true' if report.valid else 'false'}`",
        "",
        "| date | pair_id | ref_version | model | spread | p50 | accepted |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| {row.date} | `{row.pair_id}` | `{row.ref_version}` | `{row.model_version}` | {row.spread:.3f} | {row.p50:.3f} | {'yes' if row.accepted else 'no'} |"
        for row in report.rows
    )
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report.errors)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
