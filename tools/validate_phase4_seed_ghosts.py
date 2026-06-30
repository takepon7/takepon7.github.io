from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile

from PIL import Image

from gitai_phase0.competition_repositories import JsonSeedGhostRepository, SqliteSubmissionRepository
from gitai_phase0.drawing_verification import CanvasStrokeReplayVerifier, parse_stroke_log
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SeedGhostDailyRow:
    date: str
    pair_id: str
    seed_count: int
    score_ghost: str
    efficiency_ghost: str
    image_files_ok: bool
    replayable_stroke_logs: bool


@dataclass(frozen=True)
class SeedGhostReport:
    daily_count: int
    seed_count: int
    valid: bool
    rows: tuple[SeedGhostDailyRow, ...]
    errors: tuple[str, ...]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate seed ghost submissions against DailyPuzzle entries.")
    parser.add_argument("--daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--seed-ghosts", type=Path, default=ROOT / "data" / "competition" / "seed_ghosts.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "phase4")
    parser.add_argument("--season-id", default="season-1")
    args = parser.parse_args()

    report = build_report(
        daily_puzzles_path=args.daily_puzzles,
        pairs_path=args.pairs,
        seed_ghosts_path=args.seed_ghosts,
        season_id=args.season_id,
    )
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "seed_ghosts.json"
    markdown_path = out_dir / "seed_ghosts.md"
    json_path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    if not report.valid:
        raise SystemExit(1)


def build_report(
    daily_puzzles_path: Path = ROOT / "data" / "puzzle" / "daily_puzzles.json",
    pairs_path: Path = ROOT / "data" / "scoring" / "pairs.json",
    seed_ghosts_path: Path = ROOT / "data" / "competition" / "seed_ghosts.json",
    season_id: str = "season-1",
) -> SeedGhostReport:
    daily = DailyPuzzleRepository(daily_puzzles_path).list()
    pairs = PairRepository(pairs_path)
    ghosts = JsonSeedGhostRepository(seed_ghosts_path).all()
    verifier = CanvasStrokeReplayVerifier()
    with tempfile.TemporaryDirectory(prefix="gitai-seed-ghosts-") as tmpdir:
        repo = SqliteSubmissionRepository(Path(tmpdir) / "seed-ghosts.sqlite")
        repo.seed(ghosts)
        rows: list[SeedGhostDailyRow] = []
        errors: list[str] = []
        for puzzle in daily:
            records = [record for record in ghosts if record.puzzle_date == puzzle.date]
            image_files_ok = all(image_ref_exists(record.image_ref) for record in records)
            replayable_stroke_logs = all(
                seed_ghost_replay_ok(record=record, pairs=pairs, verifier=verifier) for record in records
            )
            if len(records) < 2:
                errors.append(f"{puzzle.date.isoformat()}: expected at least 2 seed ghosts")
            if any(record.pair_id != puzzle.pair_id for record in records):
                errors.append(f"{puzzle.date.isoformat()}: pair_id mismatch")
            if any(record.ref_version != puzzle.ref_version for record in records):
                errors.append(f"{puzzle.date.isoformat()}: ref_version mismatch")
            if not image_files_ok:
                errors.append(f"{puzzle.date.isoformat()}: seed ghost image file missing")
            if not replayable_stroke_logs:
                errors.append(f"{puzzle.date.isoformat()}: seed ghost stroke_log is not replayable")
            score = repo.leaderboard(puzzle.date, season_id=season_id, kind="score", limit=1)
            efficiency = repo.leaderboard(puzzle.date, season_id=season_id, kind="efficiency", limit=1)
            if not score:
                errors.append(f"{puzzle.date.isoformat()}: score ghost missing")
            if not efficiency:
                errors.append(f"{puzzle.date.isoformat()}: efficiency ghost missing")
            rows.append(
                SeedGhostDailyRow(
                    date=puzzle.date.isoformat(),
                    pair_id=puzzle.pair_id,
                    seed_count=len(records),
                    score_ghost=score[0].submission_id if score else "",
                    efficiency_ghost=efficiency[0].submission_id if efficiency else "",
                    image_files_ok=image_files_ok,
                    replayable_stroke_logs=replayable_stroke_logs,
                )
            )
    return SeedGhostReport(
        daily_count=len(daily),
        seed_count=len(ghosts),
        valid=not errors and len(ghosts) >= len(daily) * 2,
        rows=tuple(rows),
        errors=tuple(errors),
    )


def image_ref_exists(image_ref: str) -> bool:
    return image_ref_path(image_ref).exists() if image_ref_path(image_ref) else False


def image_ref_path(image_ref: str) -> Path | None:
    if not image_ref.startswith("file:"):
        return None
    path = Path(image_ref.removeprefix("file:"))
    if path.is_absolute():
        return path
    return ROOT / path


def seed_ghost_replay_ok(record, pairs: PairRepository, verifier: CanvasStrokeReplayVerifier) -> bool:
    image_path = image_ref_path(record.image_ref)
    if image_path is None or not image_path.exists():
        return False
    parsed = parse_stroke_log(record.stroke_log, max_strokes=250, max_points_per_stroke=2000)
    if parsed is None or len(parsed) != record.stroke_count:
        return False
    try:
        pair = pairs.get(record.pair_id)
        with Image.open(image_path) as image:
            result = verifier.verify(image.convert("RGBA"), pair, record.stroke_log)
    except (OSError, KeyError):
        return False
    return result.accepted


def render_markdown(report: SeedGhostReport) -> str:
    lines = [
        "# Phase 4 seed ghosts",
        "",
        f"- daily_count: `{report.daily_count}`",
        f"- seed_count: `{report.seed_count}`",
        f"- valid: `{'true' if report.valid else 'false'}`",
        "",
        "| date | pair_id | seed_count | score_ghost | efficiency_ghost | images | replay |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row.date} | `{row.pair_id}` | {row.seed_count} | `{row.score_ghost}` | `{row.efficiency_ghost}` | {'ok' if row.image_files_ok else 'missing'} | {'ok' if row.replayable_stroke_logs else 'missing'} |"
        for row in report.rows
    )
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report.errors)
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
