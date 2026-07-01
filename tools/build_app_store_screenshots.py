from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "reports" / "app_store" / "screenshots"
DEVICE_SIZE = (1290, 2796)
RAW_SIZE = (430, 932)
FONT_CANDIDATES = (
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)

FRAMES = [
    {
        "name": "01",
        "headline": ["AI鑑定士を", "だませ"],
        "accent_line": 1,
        "background": "#244f43",
        "screen": "home",
    },
    {
        "name": "02",
        "headline": ["毎日変わる", "擬態お題"],
        "accent_line": 1,
        "background": "#315f9d",
        "screen": "daily",
    },
    {
        "name": "03",
        "headline": ["スコアで", "競える"],
        "accent_line": 1,
        "background": "#d6453d",
        "screen": "score",
    },
    {
        "name": "04",
        "headline": ["ゴーストに", "挑戦"],
        "accent_line": 1,
        "background": "#2f875a",
        "screen": "ghost",
    },
    {
        "name": "05",
        "headline": ["結果を", "シェア"],
        "accent_line": 1,
        "background": "#1f1d1a",
        "screen": "share",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build App Store 6.9-inch screenshots.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    build_app_store_screenshots(args.out_dir)
    print(f"Wrote screenshots to {args.out_dir / 'generated' / 'iphone-6.9'}")


def build_app_store_screenshots(out_dir: Path = DEFAULT_OUT_DIR) -> None:
    raw_dir = out_dir / "raw"
    final_dir = out_dir / "generated" / "iphone-6.9"
    raw_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    for frame in FRAMES:
        raw = render_raw_screen(str(frame["screen"]))
        raw_path = raw_dir / f"{frame['name']}-{frame['screen']}.png"
        raw.save(raw_path)
        final = compose_store_frame(raw, frame)
        final.save(final_dir / f"{frame['name']}.png")


def compose_store_frame(raw: Image.Image, frame: dict) -> Image.Image:
    canvas = Image.new("RGB", DEVICE_SIZE, str(frame["background"]))
    draw = ImageDraw.Draw(canvas)
    headline_font = font(108)
    accent_font = font(122)
    foreground = "#fffaf0"
    accent = "#e7c24e"

    y = 168
    for index, line in enumerate(frame["headline"]):
        current_font = accent_font if index == frame["accent_line"] else headline_font
        color = accent if index == frame["accent_line"] else foreground
        line_width = draw.textlength(line, font=current_font)
        draw.text(((DEVICE_SIZE[0] - line_width) / 2, y), line, font=current_font, fill=color)
        y += 132

    phone_w = 920
    scale = phone_w / RAW_SIZE[0]
    phone_h = int(RAW_SIZE[1] * scale)
    phone_x = (DEVICE_SIZE[0] - phone_w) // 2
    phone_y = 650
    draw_phone_frame(canvas, (phone_x, phone_y), (phone_w, phone_h), raw)
    return canvas


def render_raw_screen(kind: str) -> Image.Image:
    image = Image.new("RGB", RAW_SIZE, "#f7f2e7")
    draw = ImageDraw.Draw(image)
    title_font = font(28)
    label_font = font(14)
    body_font = font(18)
    small_font = font(12)

    rounded(draw, (16, 18, 414, 78), 18, "#244f43")
    draw.text((34, 29), "gitai", font=title_font, fill="#fffaf0")
    draw.text((330, 38), "接続済み", font=small_font, fill="#e7c24e")

    if kind in {"home", "daily", "score"}:
        draw.text((26, 104), "Daily", font=label_font, fill="#6b6258")
        draw.text((26, 128), "orange → tennis ball", font=body_font, fill="#1f1d1a")
        draw.text((26, 156), "素体を別のモノに化けさせよう", font=small_font, fill="#6b6258")
        canvas_box = (26, 196, 404, 574)
        rounded(draw, canvas_box, 22, "#ffffff")
        draw_reference(draw, canvas_box)
        if kind == "score":
            draw_disguise_lines(draw, canvas_box)
        controls(draw, 26, 594)

    if kind == "daily":
        daily_panel(draw, 26, 690)
    elif kind == "score":
        score_panel(draw, 26, 690)
    elif kind == "ghost":
        ghost_panel(draw, 26, 104)
    elif kind == "share":
        share_panel(image, draw, 26, 104)
    else:
        leaderboard_panel(draw, 26, 690)

    return image


def draw_phone_frame(canvas: Image.Image, xy: tuple[int, int], size: tuple[int, int], raw: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    x, y = xy
    w, h = size
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    rounded(shadow_draw, (x + 18, y + 26, x + w + 18, y + h + 26), 86, (0, 0, 0, 80))
    canvas.paste(Image.alpha_composite(Image.new("RGBA", canvas.size, (0, 0, 0, 0)), shadow).convert("RGB"), mask=shadow.split()[-1])
    rounded(draw, (x, y, x + w, y + h), 86, "#101010")
    rounded(draw, (x + 28, y + 28, x + w - 28, y + h - 28), 58, "#f7f2e7")
    raw_resized = raw.resize((w - 56, h - 56), Image.Resampling.LANCZOS)
    mask = Image.new("L", raw_resized.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, raw_resized.size[0], raw_resized.size[1]), radius=46, fill=255)
    canvas.paste(raw_resized, (x + 28, y + 28), mask)
    rounded(draw, (x + w // 2 - 98, y + 42, x + w // 2 + 98, y + 70), 16, "#101010")


def draw_reference(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    draw.ellipse((cx - 90, cy - 95, cx + 90, cy + 95), fill="#e88b2f", outline="#b85b22", width=5)
    draw.arc((cx - 98, cy - 104, cx + 98, cy + 104), 62, 296, fill="#fffaf0", width=8)
    draw.arc((cx - 98, cy - 104, cx + 98, cy + 104), 244, 116, fill="#fffaf0", width=8)


def draw_disguise_lines(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    draw.line((cx - 105, cy - 20, cx + 105, cy - 20), fill="#1f1d1a", width=8)
    draw.line((cx - 70, cy + 62, cx + 70, cy + 62), fill="#1f1d1a", width=8)
    draw.line((cx - 38, cy - 82, cx + 45, cy + 86), fill="#315f9d", width=7)
    draw.line((cx + 42, cy - 82, cx - 44, cy + 86), fill="#315f9d", width=7)


def controls(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    labels = [("Draw", "#1f1d1a"), ("Erase", "#fffaf0"), ("Submit", "#e7c24e")]
    current_x = x
    for label, color in labels:
        width = 112 if label != "Submit" else 132
        rounded(draw, (current_x, y, current_x + width, y + 48), 16, "#244f43" if label == "Submit" else "#ece4d6")
        draw.text((current_x + 18, y + 14), label, font=font(13), fill=color if label == "Submit" else "#1f1d1a")
        current_x += width + 14


def leaderboard_panel(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    card(draw, x, y, 378, 186, "Top Ghost")
    rows = [("#1", "mika", "087 / Top 4%"), ("#2", "guest", "073 / Top 11%"), ("#3", "sora", "061 / Top 22%")]
    for idx, row in enumerate(rows):
        yy = y + 52 + idx * 38
        draw.text((x + 22, yy), row[0], font=font(15), fill="#244f43")
        draw.text((x + 72, yy), row[1], font=font(15), fill="#1f1d1a")
        draw.text((x + 228, yy), row[2], font=font(13), fill="#6b6258")


def daily_panel(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    card(draw, x, y, 378, 186, "Daily Archive")
    rows = ["06/30 balloon → baseball", "07/01 orange → tennis ball", "07/02 tomato → baseball"]
    for idx, row in enumerate(rows):
        yy = y + 54 + idx * 42
        rounded(draw, (x + 18, yy - 8, x + 360, yy + 26), 12, "#fffaf0" if idx == 1 else "#f1eadc")
        draw.text((x + 32, yy), row, font=font(13), fill="#1f1d1a")


def score_panel(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    card(draw, x, y, 378, 188, "Result")
    draw.text((x + 26, y + 48), "087", font=font(64), fill="#244f43")
    draw.text((x + 166, y + 64), "Top 4%", font=font(28), fill="#d6453d")
    draw.text((x + 28, y + 132), "これは見事なtennis ballです。", font=font(15), fill="#1f1d1a")


def ghost_panel(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    card(draw, x, y, 378, 286, "Ghost Replay")
    rounded(draw, (x + 28, y + 58, x + 350, y + 234), 18, "#ffffff")
    draw_reference(draw, (x + 92, y + 70, x + 286, y + 218))
    draw_disguise_lines(draw, (x + 92, y + 70, x + 286, y + 218))
    draw.text((x + 28, y + 246), "#1 mika / 087 / Funny 4", font=font(15), fill="#1f1d1a")
    rounded(draw, (x + 246, y + 240, x + 350, y + 272), 12, "#244f43")
    draw.text((x + 274, y + 248), "Replay", font=font(12), fill="#fffaf0")
    leaderboard_panel(draw, x, y + 320)


def share_panel(image: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    card(draw, x, y, 378, 540, "Share Card")
    share_path = ROOT / "web" / "public" / "brand" / "share-cards" / "share-card-example-2026-07-01-orange_to_tennis_ball.png"
    if share_path.exists():
        share = Image.open(share_path).convert("RGB")
        share.thumbnail((248, 440), Image.Resampling.LANCZOS)
        left = x + (378 - share.width) // 2
        draw.rounded_rectangle((left - 6, y + 58 - 6, left + share.width + 6, y + 58 + share.height + 6), radius=20, fill="#1f1d1a")
        mask = Image.new("L", share.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, share.width, share.height), radius=18, fill=255)
        image.paste(share, (left, y + 58), mask)
    rounded(draw, (x + 94, y + 474, x + 284, y + 520), 16, "#244f43")
    draw.text((x + 142, y + 488), "Share", font=font(15), fill="#fffaf0")


def card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str) -> None:
    rounded(draw, (x, y, x + w, y + h), 22, "#ffffff")
    draw.text((x + 22, y + 18), title, font=font(18), fill="#244f43")


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        candidate = Path(path)
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


if __name__ == "__main__":
    main()
