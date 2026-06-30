from __future__ import annotations

import json
from pathlib import Path

from PIL import ImageDraw

from gitai_phase0.drawing_verification import (
    CanvasStrokeReplayVerifier,
    SUPPORTED_BASE_RENDERER_IDS,
    parse_stroke_log,
    render_base,
    render_replay,
)
from gitai_phase0.repositories import PairRepository


def test_canvas_stroke_replay_verifier_accepts_replayed_image() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")
    stroke_log = sample_stroke_log()
    strokes = parse_stroke_log(stroke_log, max_strokes=250, max_points_per_stroke=2000)
    assert strokes is not None
    image = render_replay(pair, strokes, (768, 768))

    result = CanvasStrokeReplayVerifier().verify(image, pair, stroke_log)
    assert result.accepted is True
    assert result.distance == 0.0


def test_canvas_stroke_replay_verifier_rejects_pasted_image() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")
    stroke_log = sample_stroke_log()
    strokes = parse_stroke_log(stroke_log, max_strokes=250, max_points_per_stroke=2000)
    assert strokes is not None
    image = render_replay(pair, strokes, (768, 768))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((170, 170, 598, 598), fill=(0, 0, 0, 255))

    result = CanvasStrokeReplayVerifier().verify(image, pair, stroke_log)
    assert result.accepted is False
    assert result.reason == "submitted image does not match stroke replay"


def test_canvas_stroke_replay_verifier_rejects_invalid_log() -> None:
    pair = PairRepository(Path("data/scoring/pairs.json")).get("apple_to_baseball")
    image = render_replay(pair, [], (768, 768))

    result = CanvasStrokeReplayVerifier().verify(image, pair, {"strokes": [{"points": [1, 2, 3]}]})
    assert result.accepted is False
    assert result.reason == "stroke_log is not replayable"


def test_replay_renderer_covers_daily_base_objects() -> None:
    pairs = {
        item["pair_id"]: item
        for item in json.loads(Path("data/scoring/pairs.json").read_text(encoding="utf-8"))["pairs"]
    }
    daily_base_ids = {
        pairs[item["pair_id"]]["base"]["object_id"]
        for item in json.loads(Path("data/puzzle/daily_puzzles.json").read_text(encoding="utf-8"))["daily_puzzles"]
    }

    assert daily_base_ids <= SUPPORTED_BASE_RENDERER_IDS


def test_daily_base_renderers_are_object_specific() -> None:
    generic_center = (233, 229, 216, 255)
    for object_id in ("apple", "balloon", "book", "chair", "mug", "orange", "tomato"):
        image = render_base(object_id, (256, 256))

        assert image.getpixel((128, 128)) != generic_center


def sample_stroke_log() -> dict:
    return {
        "strokes": [
            {
                "color": "#315f9d",
                "size": 26,
                "mode": "draw",
                "points": [
                    {"x": 250, "y": 330, "t": 1, "pressure": 0.5},
                    {"x": 360, "y": 300, "t": 2, "pressure": 0.5},
                    {"x": 490, "y": 330, "t": 3, "pressure": 0.5},
                ],
            },
            {
                "color": "#1f1d1a",
                "size": 10,
                "mode": "erase",
                "points": [
                    {"x": 340, "y": 200, "t": 4, "pressure": 0.5},
                    {"x": 395, "y": 250, "t": 5, "pressure": 0.5},
                ],
            },
        ]
    }
