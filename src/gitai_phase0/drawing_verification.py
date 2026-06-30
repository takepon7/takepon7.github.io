from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from gitai_phase0.application import DrawingVerification
from gitai_phase0.domain import PairSpec


SUPPORTED_BASE_RENDERER_IDS = frozenset(
    {
        "apple",
        "orange",
        "tomato",
        "tennis_ball",
        "balloon",
        "banana",
        "mug",
        "book",
        "car",
        "chair",
    }
)


@dataclass(frozen=True)
class CanvasStrokeReplayVerifier:
    max_mean_abs_error: float = 0.08
    compare_size: int = 96
    max_strokes: int = 250
    max_points_per_stroke: int = 2000

    def verify(
        self,
        image: Image.Image,
        pair: PairSpec,
        stroke_log: dict[str, Any] | None,
    ) -> DrawingVerification:
        parsed = parse_stroke_log(stroke_log, self.max_strokes, self.max_points_per_stroke)
        if parsed is None:
            return DrawingVerification(False, 1.0, "stroke_log is not replayable")
        replayed = render_replay(pair=pair, strokes=parsed, size=image.size)
        distance = mean_abs_error(image.convert("RGBA"), replayed, self.compare_size)
        if distance > self.max_mean_abs_error:
            return DrawingVerification(False, distance, "submitted image does not match stroke replay")
        return DrawingVerification(True, distance, "ok")


@dataclass(frozen=True)
class ReplayStroke:
    color: tuple[int, int, int, int]
    size: int
    mode: str
    points: tuple[tuple[float, float], ...]


def parse_stroke_log(
    stroke_log: dict[str, Any] | None,
    max_strokes: int,
    max_points_per_stroke: int,
) -> list[ReplayStroke] | None:
    if not isinstance(stroke_log, dict):
        return None
    raw_strokes = stroke_log.get("strokes")
    if not isinstance(raw_strokes, list) or len(raw_strokes) > max_strokes:
        return None

    strokes: list[ReplayStroke] = []
    for raw in raw_strokes:
        if not isinstance(raw, dict):
            return None
        mode = str(raw.get("mode", "draw"))
        if mode not in {"draw", "erase"}:
            return None
        color = parse_color(str(raw.get("color", "#1f1d1a")))
        if color is None:
            return None
        try:
            size = int(round(float(raw.get("size", 1))))
        except (TypeError, ValueError):
            return None
        if size < 1 or size > 128:
            return None
        points = raw.get("points")
        if not isinstance(points, list) or len(points) > max_points_per_stroke:
            return None
        parsed_points: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, dict):
                return None
            try:
                parsed_points.append((float(point["x"]), float(point["y"])))
            except (KeyError, TypeError, ValueError):
                return None
        if parsed_points:
            strokes.append(
                ReplayStroke(
                    color=color,
                    size=size,
                    mode=mode,
                    points=tuple(parsed_points),
                )
            )
    return strokes


def parse_color(value: str) -> tuple[int, int, int, int] | None:
    if not value.startswith("#") or len(value) != 7:
        return None
    try:
        return (
            int(value[1:3], 16),
            int(value[3:5], 16),
            int(value[5:7], 16),
            255,
        )
    except ValueError:
        return None


def render_replay(pair: PairSpec, strokes: list[ReplayStroke], size: tuple[int, int]) -> Image.Image:
    image = render_base(pair.base.object_id, size)
    for stroke in strokes:
        apply_stroke(image, stroke)
    return image


def render_base(object_id: str, size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = size
    if object_id == "apple":
        draw_apple(draw, width, height)
    elif object_id == "orange":
        draw_round_fruit(draw, width, height, (232, 139, 47, 255), leafy=False)
    elif object_id == "tomato":
        draw_round_fruit(draw, width, height, (215, 71, 47, 255), leafy=True)
    elif object_id == "tennis_ball":
        draw_tennis_ball(draw, width, height)
    elif object_id == "balloon":
        draw_balloon(draw, width, height)
    elif object_id == "banana":
        draw_banana(draw, width, height)
    elif object_id == "mug":
        draw_mug(draw, width, height)
    elif object_id == "book":
        draw_book(draw, width, height)
    elif object_id == "car":
        draw_car(draw, width, height)
    elif object_id == "chair":
        draw_chair(draw, width, height)
    else:
        draw_generic_base(draw, width, height)
    return image


def draw_apple(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    sx = width / 512
    sy = height / 512
    sr = min(sx, sy)
    draw.rounded_rectangle(scale_box((238, 74, 276, 154), sx, sy), radius=int(16 * sr), fill=(108, 59, 34, 255))
    draw.ellipse(scale_box((264, 90, 340, 126), sx, sy), fill=(85, 146, 70, 255))
    draw.ellipse(scale_box((104, 124, 288, 388), sx, sy), fill=(210, 47, 53, 255))
    draw.ellipse(scale_box((224, 124, 408, 388), sx, sy), fill=(210, 47, 53, 255))
    draw.rectangle(scale_box((170, 258, 342, 400), sx, sy), fill=(210, 47, 53, 255))


def draw_round_fruit(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    color: tuple[int, int, int, int],
    leafy: bool,
) -> None:
    draw.ellipse(
        (
            width * 0.24,
            height * 0.25,
            width * 0.76,
            height * 0.81,
        ),
        fill=color,
    )
    if not leafy:
        return
    for index, dx in enumerate((-0.06, -0.03, 0.0, 0.03, 0.06)):
        y_offset = abs(index - 2) * height * 0.01
        draw.ellipse(
            (
                width * (0.46 + dx),
                height * 0.18 + y_offset,
                width * (0.54 + dx),
                height * 0.38,
            ),
            fill=(47, 135, 90, 255),
        )


def draw_tennis_ball(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    radius = width * 0.28
    cx = width / 2
    cy = height / 2
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(217, 223, 74, 255))
    line_width = max(1, int(width * 0.035))
    left = (width * 0.10, cy - width * 0.25, width * 0.60, cy + width * 0.25)
    right = (width * 0.40, cy - width * 0.25, width * 0.90, cy + width * 0.25)
    draw.arc(left, start=270, end=90, fill=(247, 245, 238, 255), width=line_width)
    draw.arc(right, start=90, end=270, fill=(247, 245, 238, 255), width=line_width)


def draw_balloon(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.ellipse(
        (
            width * 0.26,
            height * 0.10,
            width * 0.74,
            height * 0.70,
        ),
        fill=(215, 71, 47, 255),
    )
    draw.polygon(
        [
            (width * 0.50, height * 0.70),
            (width * 0.47, height * 0.76),
            (width * 0.53, height * 0.76),
        ],
        fill=(139, 69, 56, 255),
    )
    draw.line(
        [
            (width * 0.50, height * 0.76),
            (width * 0.45, height * 0.86),
            (width * 0.55, height * 0.92),
            (width * 0.50, height * 0.98),
        ],
        fill=(95, 87, 77, 255),
        width=max(1, int(width * 0.012)),
        joint="curve",
    )


def draw_banana(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    line_width = max(1, int(width * 0.12))
    draw.line(
        [
            (width * 0.28, height * 0.58),
            (width * 0.52, height * 0.76),
            (width * 0.76, height * 0.42),
        ],
        fill=(227, 189, 50, 255),
        width=line_width,
        joint="curve",
    )
    tip_width = max(1, int(width * 0.025))
    draw.line(
        [
            (width * 0.25, height * 0.56),
            (width * 0.20, height * 0.54),
        ],
        fill=(139, 106, 31, 255),
        width=tip_width,
    )
    draw.line(
        [
            (width * 0.78, height * 0.40),
            (width * 0.83, height * 0.36),
        ],
        fill=(139, 106, 31, 255),
        width=tip_width,
    )


def draw_mug(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    line_width = max(1, int(width * 0.025))
    draw.rounded_rectangle(
        (
            width * 0.30,
            height * 0.32,
            width * 0.62,
            height * 0.66,
        ),
        radius=int(width * 0.04),
        fill=(255, 253, 247, 255),
        outline=(43, 39, 34, 255),
        width=line_width,
    )
    draw.arc(
        (
            width * 0.54,
            height * 0.37,
            width * 0.76,
            height * 0.59,
        ),
        start=270,
        end=90,
        fill=(43, 39, 34, 255),
        width=line_width,
    )


def draw_book(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.rounded_rectangle(
        (
            width * 0.27,
            height * 0.25,
            width * 0.73,
            height * 0.75,
        ),
        radius=int(width * 0.025),
        fill=(49, 95, 157, 255),
    )
    draw.line(
        [
            (width * 0.38, height * 0.25),
            (width * 0.38, height * 0.75),
        ],
        fill=(255, 253, 247, 255),
        width=max(1, int(width * 0.018)),
    )


def draw_car(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.rounded_rectangle(
        (
            width * 0.22,
            height * 0.45,
            width * 0.78,
            height * 0.61,
        ),
        radius=int(width * 0.04),
        fill=(215, 71, 47, 255),
    )
    draw.polygon(
        [
            (width * 0.36, height * 0.45),
            (width * 0.45, height * 0.34),
            (width * 0.60, height * 0.34),
            (width * 0.68, height * 0.45),
        ],
        fill=(215, 71, 47, 255),
    )
    wheel_radius = width * 0.055
    for cx in (width * 0.34, width * 0.66):
        cy = height * 0.62
        draw.ellipse(
            (cx - wheel_radius, cy - wheel_radius, cx + wheel_radius, cy + wheel_radius),
            fill=(43, 39, 34, 255),
        )


def draw_chair(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    line_width = max(1, int(width * 0.035))
    outline = (108, 59, 34, 255)
    fill = (139, 90, 50, 255)
    draw.rounded_rectangle(
        (
            width * 0.34,
            height * 0.30,
            width * 0.66,
            height * 0.52,
        ),
        radius=int(width * 0.02),
        fill=fill,
        outline=outline,
        width=line_width,
    )
    draw.rounded_rectangle(
        (
            width * 0.31,
            height * 0.52,
            width * 0.69,
            height * 0.64,
        ),
        radius=int(width * 0.02),
        fill=fill,
        outline=outline,
        width=line_width,
    )
    draw.line([(width * 0.36, height * 0.64), (width * 0.30, height * 0.82)], fill=outline, width=line_width)
    draw.line([(width * 0.64, height * 0.64), (width * 0.70, height * 0.82)], fill=outline, width=line_width)


def draw_generic_base(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    scale = min(width, height)
    cx = width / 2
    cy = height / 2
    radius = scale * 0.28
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(233, 229, 216, 255),
    )


def scale_box(box: tuple[int, int, int, int], sx: float, sy: float) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    return (x1 * sx, y1 * sy, x2 * sx, y2 * sy)


def apply_stroke(image: Image.Image, stroke: ReplayStroke) -> None:
    if stroke.mode == "erase":
        erase_stroke(image, stroke)
        return
    draw = ImageDraw.Draw(image, "RGBA")
    draw_stroke(draw, stroke, fill=stroke.color)


def erase_stroke(image: Image.Image, stroke: ReplayStroke) -> None:
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw_stroke(draw, stroke, fill=255)
    alpha = image.getchannel("A")
    image.putalpha(ImageChops.subtract(alpha, mask))


def draw_stroke(draw: ImageDraw.ImageDraw, stroke: ReplayStroke, fill) -> None:
    radius = stroke.size / 2
    first = stroke.points[0]
    draw.ellipse(
        (first[0] - radius, first[1] - radius, first[0] + radius, first[1] + radius),
        fill=fill,
    )
    if len(stroke.points) < 2:
        return
    draw.line(stroke.points, fill=fill, width=stroke.size, joint="curve")
    for point in stroke.points[1:]:
        draw.ellipse(
            (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius),
            fill=fill,
        )


def mean_abs_error(actual: Image.Image, expected: Image.Image, compare_size: int) -> float:
    target_size = (compare_size, compare_size)
    actual_small = actual.resize(target_size, Image.Resampling.BILINEAR)
    expected_small = expected.resize(target_size, Image.Resampling.BILINEAR)
    a = np.asarray(actual_small, dtype=np.float32)
    b = np.asarray(expected_small, dtype=np.float32)
    return float(np.abs(a - b).mean() / 255.0)
