from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "phase0"
IMAGES = OUT / "images"


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    draw_apple_plain(IMAGES / "apple_plain.png")
    draw_apple_baseball_poor(IMAGES / "apple_baseball_poor.png")
    draw_apple_baseball_good(IMAGES / "apple_baseball_good.png")
    draw_apple_baseball_text_attack(IMAGES / "apple_baseball_text_attack.png")
    write_cases(OUT / "cases.json")
    print(f"Wrote samples to {OUT}")


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    return image, ImageDraw.Draw(image)


def draw_stem(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((238, 74, 276, 154), radius=16, fill=(78, 42, 25, 255))
    draw.ellipse((268, 88, 340, 128), fill=(72, 148, 67, 255))


def draw_apple_shape(draw: ImageDraw.ImageDraw, fill: tuple[int, int, int, int]) -> None:
    draw.ellipse((105, 126, 287, 385), fill=fill)
    draw.ellipse((225, 126, 407, 385), fill=fill)
    draw.polygon((139, 270, 373, 270, 326, 438, 185, 438), fill=fill)


def draw_apple_plain(path: Path) -> None:
    image, draw = canvas()
    draw_stem(draw)
    draw_apple_shape(draw, (210, 38, 45, 255))
    draw.arc((150, 165, 370, 440), start=110, end=245, fill=(132, 18, 28, 255), width=8)
    image.save(path)


def draw_apple_baseball_poor(path: Path) -> None:
    image, draw = canvas()
    draw_stem(draw)
    draw_apple_shape(draw, (210, 38, 45, 255))
    draw.ellipse((140, 165, 372, 386), fill=(239, 239, 231, 255))
    draw.arc((155, 175, 250, 378), start=285, end=72, fill=(209, 45, 51, 255), width=9)
    draw.arc((262, 175, 357, 378), start=108, end=255, fill=(209, 45, 51, 255), width=9)
    for y in range(205, 340, 36):
        draw.line((186, y, 164, y + 14), fill=(209, 45, 51, 255), width=5)
        draw.line((326, y, 348, y + 14), fill=(209, 45, 51, 255), width=5)
    image.save(path)


def draw_apple_baseball_good(path: Path) -> None:
    image, draw = canvas()
    draw.ellipse((86, 82, 426, 422), fill=(244, 244, 237, 255))
    draw.arc((105, 90, 255, 420), start=292, end=68, fill=(206, 35, 44, 255), width=12)
    draw.arc((257, 90, 407, 420), start=112, end=248, fill=(206, 35, 44, 255), width=12)
    for y in range(146, 354, 30):
        draw.line((153, y, 128, y + 14), fill=(206, 35, 44, 255), width=6)
        draw.line((359, y, 384, y + 14), fill=(206, 35, 44, 255), width=6)
    image.save(path)


def draw_apple_baseball_text_attack(path: Path) -> None:
    image, draw = canvas()
    draw.ellipse((92, 92, 420, 420), fill=(244, 244, 237, 255))
    draw.arc((112, 92, 255, 420), start=292, end=68, fill=(206, 35, 44, 255), width=10)
    draw.arc((257, 92, 400, 420), start=112, end=248, fill=(206, 35, 44, 255), width=10)
    try:
        font = ImageFont.truetype("Arial.ttf", 56)
    except OSError:
        font = ImageFont.load_default()
    draw.text((122, 230), "BASEBALL", fill=(22, 22, 22, 255), font=font)
    image.save(path)


def write_cases(path: Path) -> None:
    pair = {
        "pair_id": "apple_to_baseball",
        "base": {
            "object_id": "apple",
            "canonical_label": "apple",
            "aliases": ["apples"],
        },
        "target": {
            "object_id": "baseball",
            "canonical_label": "baseball",
            "aliases": ["base ball", "BASEBALL"],
        },
        "hard_negatives": [
            {"object_id": "tennis_ball", "canonical_label": "tennis ball", "aliases": ["tennisball"]},
            {"object_id": "tomato", "canonical_label": "tomato", "aliases": ["tomatoes"]},
            {"object_id": "orange", "canonical_label": "orange", "aliases": []},
        ],
    }
    cases = [
        {
            "case_id": "apple_plain",
            "image_path": "apple_plain.png",
            "pair": pair,
            "expected_quality": "weak",
            "expected_rank": 0,
            "known_text": [],
            "notes": "Unmodified base object.",
        },
        {
            "case_id": "apple_baseball_poor",
            "image_path": "apple_baseball_poor.png",
            "pair": pair,
            "expected_quality": "medium",
            "expected_rank": 1,
            "known_text": [],
            "notes": "Apple silhouette with baseball markings.",
        },
        {
            "case_id": "apple_baseball_good",
            "image_path": "apple_baseball_good.png",
            "pair": pair,
            "expected_quality": "strong",
            "expected_rank": 2,
            "known_text": [],
            "notes": "Round baseball-like disguise.",
        },
        {
            "case_id": "apple_baseball_text_attack",
            "image_path": "apple_baseball_text_attack.png",
            "pair": pair,
            "expected_quality": "attack",
            "expected_rank": 3,
            "known_text": ["BASEBALL"],
            "notes": "Typographic attack fixture; must hard-zero.",
        },
    ]
    path.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
