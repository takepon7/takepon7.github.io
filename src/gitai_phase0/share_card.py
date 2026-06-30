from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from gitai_phase0.commentary import AppraisalComment, comment_for_submission
from gitai_phase0.competition import SubmissionRecord
from gitai_phase0.domain import PairSpec


CARD_SIZE = (1080, 1920)


@dataclass(frozen=True)
class ShareCard:
    png: bytes
    filename: str


def build_share_card(
    submission: SubmissionRecord,
    pair: PairSpec,
    image_bytes: bytes,
    comment: AppraisalComment | None = None,
    season_label: str = "",
    public_url: str = "",
) -> ShareCard:
    art = Image.open(BytesIO(image_bytes)).convert("RGBA")
    appraisal = comment or comment_for_submission(submission, pair)
    card = Image.new("RGBA", CARD_SIZE, (247, 245, 238, 255))
    draw = ImageDraw.Draw(card)

    title_font = font(72, bold=True)
    subtitle_font = font(34, bold=True)
    body_font = font(42, bold=True)
    small_font = font(28, bold=True)
    score_font = font(168, bold=True)

    draw.rectangle((0, 0, 1080, 220), fill=(35, 32, 29, 255))
    draw.text((64, 46), "gitai", fill=(255, 253, 247, 255), font=title_font)
    draw.text((64, 132), "AIを騙すデイリー擬態", fill=(232, 224, 207, 255), font=subtitle_font)

    art_box = (102, 292, 978, 1168)
    draw.rounded_rectangle((92, 282, 988, 1178), radius=34, fill=(255, 255, 255, 255), outline=(215, 204, 184, 255), width=4)
    fitted = fit_cover(art, art_box[2] - art_box[0], art_box[3] - art_box[1])
    card.alpha_composite(fitted, (art_box[0], art_box[1]))

    draw.rounded_rectangle((92, 1228, 988, 1690), radius=32, fill=mood_color(appraisal.mood))
    draw.text((136, 1266), f"{pair.base.canonical_label} -> {pair.target.canonical_label}", fill=(255, 253, 247, 255), font=body_font)
    draw_wrapped_text(draw, appraisal.line, (136, 1330), subtitle_font, max_chars=24, line_gap=8)
    draw.text((136, 1434), str(submission.score).zfill(3), fill=(255, 253, 247, 255), font=score_font)
    draw.text(
        (520, 1484),
        top_percentile_label(submission.percentile),
        fill=(230, 238, 232, 255),
        font=body_font,
    )
    draw.text((136, 1606), f"{submission.player.display_name} / {submission.stroke_count} strokes", fill=(224, 235, 228, 255), font=small_font)

    draw.text((92, 1750), "今日のお題に挑戦", fill=(35, 32, 29, 255), font=body_font)
    footer = season_label or submission.season_id
    draw.text((92, 1814), footer, fill=(111, 64, 54, 255), font=small_font)
    draw.text((92, 1856), public_url or "gitai", fill=(111, 64, 54, 255), font=small_font)

    out = BytesIO()
    card.convert("RGB").save(out, format="PNG", optimize=True)
    return ShareCard(png=out.getvalue(), filename=f"gitai-{submission.submission_id}.png")


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_chars: int,
    line_gap: int,
) -> None:
    x, y = xy
    lines = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    for line in lines[:3]:
        draw.text((x, y), line, fill=(230, 238, 232, 255), font=font)
        y += font.size + line_gap if hasattr(font, "size") else 42


def mood_color(mood: str) -> tuple[int, int, int, int]:
    if mood == "delighted":
        return (32, 94, 73, 255)
    if mood == "suspicious":
        return (98, 73, 44, 255)
    if mood == "exasperated":
        return (104, 58, 51, 255)
    return (36, 79, 67, 255)


def top_percentile_label(percentile: float) -> str:
    clamped = max(0.0, min(1.0, percentile))
    top = max(0.0, min(100.0, (1.0 - clamped) * 100.0))
    if clamped > 0 and top < 1.0:
        return "Top 1%"
    if top < 10.0:
        return f"Top {top:.1f}%"
    return f"Top {round(top)}%"


def fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()
