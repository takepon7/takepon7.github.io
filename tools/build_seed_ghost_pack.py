from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from gitai_phase0.drawing_verification import parse_stroke_log, render_replay
from gitai_phase0.repositories import DailyPuzzleRepository, PairRepository, SeedScoreRepository, image_fingerprint

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "competition" / "seed_ghost_images"
OUT_JSON = ROOT / "data" / "competition" / "seed_ghosts.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build seed ghost submissions for DailyPuzzle entries.")
    parser.add_argument("--daily-puzzles", type=Path, default=ROOT / "data" / "puzzle" / "daily_puzzles.json")
    parser.add_argument("--pairs", type=Path, default=ROOT / "data" / "scoring" / "pairs.json")
    parser.add_argument("--seed-scores", type=Path, default=ROOT / "data" / "scoring" / "seed_scores.json")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--season-id", default="season-1")
    args = parser.parse_args()

    ghosts = build_seed_ghost_pack(
        daily_puzzles_path=args.daily_puzzles,
        pairs_path=args.pairs,
        seed_scores_path=args.seed_scores,
        out_dir=args.out_dir,
        season_id=args.season_id,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps({"seed_ghosts": ghosts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.out_json}")
    print(f"Wrote {len(ghosts)} seed ghost images to {args.out_dir}")


def build_seed_ghost_pack(
    daily_puzzles_path: Path,
    pairs_path: Path,
    seed_scores_path: Path,
    out_dir: Path,
    season_id: str = "season-1",
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    daily = DailyPuzzleRepository(daily_puzzles_path)
    pairs = PairRepository(pairs_path)
    refs = SeedScoreRepository(seed_scores_path)
    ghosts: list[dict] = []
    for puzzle in daily.list():
        pair = pairs.get(puzzle.pair_id)
        ref = refs.get(puzzle.ref_version)
        for kind, score, raw, percentile, stroke_count in (
            ("score", 960, min(1.0, ref.stats["p90"] + 0.05), 0.96, 8),
            ("fast", 760, ref.stats["p50"], 0.76, 2),
        ):
            submission_id = f"seed-{puzzle.date.isoformat()}-{puzzle.pair_id}-{kind}"
            stroke_log = build_seed_stroke_log(pair.target.object_id, kind)
            parsed = parse_stroke_log(stroke_log, max_strokes=250, max_points_per_stroke=2000)
            if parsed is None:
                raise ValueError(f"seed ghost stroke_log is not replayable: {submission_id}")
            image = render_replay(pair=pair, strokes=parsed, size=(512, 512))
            path = out_dir / f"{submission_id}.png"
            image.save(path)
            ghosts.append(
                {
                    "submission_id": submission_id,
                    "season_id": season_id,
                    "puzzle_date": puzzle.date.isoformat(),
                    "pair_id": puzzle.pair_id,
                    "ref_version": puzzle.ref_version,
                    "user_id": f"seed-ghost-{kind}",
                    "display_name": "Seed Ghost" if kind == "score" else "Fast Ghost",
                    "image_hash": image_fingerprint(image),
                    "image_ref": f"file:{relative_or_absolute(path)}",
                    "friend_code": "",
                    "stroke_count": stroke_count,
                    "stroke_log": stroke_log,
                    "score": score,
                    "percentile": percentile,
                    "raw": raw,
                    "bucket": "fooled",
                    "ocr_cheat": False,
                    "moderation": "pass",
                    "model_version": ref.model_version,
                    "created_at": datetime.combine(puzzle.date, datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                }
            )
    return ghosts


def build_seed_stroke_log(target_id: str, kind: str) -> dict[str, Any]:
    strong = kind == "score"
    if target_id == "baseball":
        return {"strokes": baseball_strokes(strong)}
    if target_id == "tennis_ball":
        return {"strokes": tennis_ball_strokes(strong)}
    if target_id == "book":
        return {"strokes": book_strokes(strong)}
    if target_id == "car":
        return {"strokes": car_strokes(strong)}
    return {"strokes": generic_strokes(strong)}


def baseball_strokes(strong: bool) -> list[dict[str, Any]]:
    if not strong:
        return [stroke("#fffdf7", 128, [(256, 256)]), stroke("#d7472f", 18, [(198, 162), (168, 256), (198, 350)])]
    return [
        stroke("#fffdf7", 128, [(256, 256)]),
        stroke("#2b2722", 10, circle_points(256, 256, 118)),
        stroke("#d7472f", 14, [(188, 148), (156, 222), (158, 298), (192, 366)]),
        stroke("#d7472f", 14, [(324, 148), (356, 222), (354, 298), (320, 366)]),
        stroke("#d7472f", 8, [(168, 214), (188, 224), (170, 236)]),
        stroke("#d7472f", 8, [(168, 276), (190, 286), (172, 298)]),
        stroke("#d7472f", 8, [(344, 214), (324, 224), (342, 236)]),
        stroke("#d7472f", 8, [(344, 276), (322, 286), (340, 298)]),
    ]


def tennis_ball_strokes(strong: bool) -> list[dict[str, Any]]:
    if not strong:
        return [stroke("#d9df4a", 128, [(256, 256)]), stroke("#fffdf7", 18, [(184, 152), (146, 256), (184, 360)])]
    return [
        stroke("#d9df4a", 128, [(256, 256)]),
        stroke("#2b2722", 9, circle_points(256, 256, 122)),
        stroke("#fffdf7", 17, [(184, 142), (142, 222), (146, 300), (190, 370)]),
        stroke("#fffdf7", 17, [(328, 142), (370, 222), (366, 300), (322, 370)]),
        stroke("#eef2a6", 24, [(230, 176), (284, 174)]),
        stroke("#c9d339", 18, [(174, 276), (210, 332)]),
        stroke("#c9d339", 18, [(338, 276), (302, 332)]),
        stroke("#f7f5ee", 8, [(206, 156), (180, 204), (174, 256)]),
    ]


def book_strokes(strong: bool) -> list[dict[str, Any]]:
    if not strong:
        return [stroke("#315f9d", 128, [(256, 258)]), stroke("#fffdf7", 18, [(208, 142), (208, 376)])]
    return [
        stroke("#315f9d", 128, [(256, 256)]),
        stroke("#315f9d", 76, [(154, 142), (154, 370), (358, 370), (358, 142), (154, 142)]),
        stroke("#2b2722", 10, [(148, 132), (364, 132), (364, 382), (148, 382), (148, 132)]),
        stroke("#fffdf7", 18, [(208, 132), (208, 382)]),
        stroke("#254a7d", 12, [(244, 182), (326, 182)]),
        stroke("#254a7d", 12, [(244, 226), (326, 226)]),
        stroke("#254a7d", 12, [(244, 270), (326, 270)]),
        stroke("#fffdf7", 8, [(168, 156), (190, 156)]),
    ]


def car_strokes(strong: bool) -> list[dict[str, Any]]:
    if not strong:
        return [stroke("#d7472f", 86, [(154, 300), (358, 300)]), stroke("#2b2722", 44, [(178, 352), (334, 352)])]
    return [
        stroke("#d7472f", 92, [(132, 300), (380, 300)]),
        stroke("#d7472f", 50, [(194, 268), (236, 220), (318, 220), (360, 268)]),
        stroke("#2b2722", 10, [(126, 258), (386, 258), (386, 340), (126, 340), (126, 258)]),
        stroke("#fffdf7", 30, [(232, 246), (310, 246)]),
        stroke("#2b2722", 48, [(178, 354)]),
        stroke("#2b2722", 48, [(334, 354)]),
        stroke("#fffdf7", 18, [(178, 354)]),
        stroke("#fffdf7", 18, [(334, 354)]),
    ]


def generic_strokes(strong: bool) -> list[dict[str, Any]]:
    if not strong:
        return [stroke("#fffdf7", 128, [(256, 256)]), stroke("#2b2722", 14, [(180, 180), (332, 332)])]
    return [
        stroke("#fffdf7", 128, [(256, 256)]),
        stroke("#2b2722", 10, circle_points(256, 256, 108)),
        stroke("#315f9d", 18, [(196, 210), (316, 210)]),
        stroke("#315f9d", 18, [(196, 256), (316, 256)]),
        stroke("#315f9d", 18, [(196, 302), (316, 302)]),
        stroke("#d7472f", 18, [(206, 198), (186, 314)]),
        stroke("#d7472f", 18, [(306, 198), (326, 314)]),
        stroke("#fffdf7", 8, [(226, 172), (286, 172)]),
    ]


def stroke(color: str, size: int, points: list[tuple[float, float]]) -> dict[str, Any]:
    return {
        "color": color,
        "size": size,
        "mode": "draw",
        "points": [{"x": x, "y": y, "t": index, "pressure": 0.5} for index, (x, y) in enumerate(points)],
    }


def circle_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    return [
        (cx, cy - radius),
        (cx + radius * 0.70, cy - radius * 0.70),
        (cx + radius, cy),
        (cx + radius * 0.70, cy + radius * 0.70),
        (cx, cy + radius),
        (cx - radius * 0.70, cy + radius * 0.70),
        (cx - radius, cy),
        (cx - radius * 0.70, cy - radius * 0.70),
        (cx, cy - radius),
    ]


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
