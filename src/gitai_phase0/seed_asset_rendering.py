from __future__ import annotations

from PIL import Image, ImageDraw

from gitai_phase0.puzzle import SeedAssetQuality

LOCAL_SEED_ASSET_MODEL = "local-deterministic-seed-asset-v1"


def render_seed_asset_image(
    base_object_id: str,
    target_object_id: str,
    quality: SeedAssetQuality,
) -> Image.Image:
    image = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw_base(draw, base_object_id)
    if quality == "medium":
        draw_disguise(draw, target_object_id, strong=False)
    elif quality == "strong":
        draw_disguise(draw, target_object_id, strong=True)
    return image


def draw_base(draw: ImageDraw.ImageDraw, object_id: str) -> None:
    if object_id == "apple":
        draw.ellipse((150, 170, 362, 410), fill="#d7472f")
        draw.rectangle((240, 95, 270, 175), fill="#6c3b22")
        draw.ellipse((275, 108, 345, 145), fill="#2f875a")
    elif object_id == "balloon":
        draw.ellipse((150, 80, 362, 345), fill="#d7472f")
        draw.polygon(((256, 345), (235, 390), (277, 390)), fill="#8b4538")
        draw.line((256, 390, 225, 470, 250, 510), fill="#5f574d", width=5)
    elif object_id == "orange":
        draw.ellipse((135, 135, 377, 377), fill="#e88b2f")
    elif object_id == "tomato":
        draw.ellipse((135, 145, 377, 390), fill="#d7472f")
        for angle in range(5):
            offset = (angle - 2) * 18
            draw.ellipse((236 + offset, 112, 276 + offset, 190), fill="#2f875a")
    elif object_id == "mug":
        draw.rounded_rectangle((150, 165, 330, 355), radius=28, fill="#fffdf7", outline="#2b2722", width=10)
        draw.arc((305, 205, 420, 320), start=-85, end=85, fill="#2b2722", width=12)
    elif object_id == "book":
        draw.rounded_rectangle((130, 105, 382, 410), radius=18, fill="#315f9d")
        draw.line((195, 105, 195, 410), fill="#fffdf7", width=9)
    elif object_id == "chair":
        draw.rounded_rectangle((170, 110, 340, 255), radius=16, fill="#8b5a32", outline="#6c3b22", width=8)
        draw.rounded_rectangle((145, 255, 365, 330), radius=16, fill="#8b5a32", outline="#6c3b22", width=8)
        draw.line((175, 330, 125, 470), fill="#6c3b22", width=12)
        draw.line((335, 330, 385, 470), fill="#6c3b22", width=12)
    else:
        draw.ellipse((150, 150, 362, 362), fill="#e9e5d8", outline="#2b2722", width=5)


def draw_disguise(draw: ImageDraw.ImageDraw, target_id: str, strong: bool) -> None:
    if target_id == "baseball":
        box = (135, 135, 377, 377) if strong else (160, 160, 352, 352)
        draw.ellipse(box, fill="#fffdf7", outline="#2b2722", width=5)
        draw.arc((105, 145, 260, 370), start=-70, end=70, fill="#d7472f", width=7)
        draw.arc((252, 145, 407, 370), start=110, end=250, fill="#d7472f", width=7)
    elif target_id == "tennis_ball":
        box = (130, 130, 382, 382) if strong else (160, 160, 352, 352)
        draw.ellipse(box, fill="#d9df4a", outline="#2b2722", width=5)
        draw.arc((105, 130, 270, 382), start=-70, end=70, fill="#fffdf7", width=9)
        draw.arc((242, 130, 407, 382), start=110, end=250, fill="#fffdf7", width=9)
    elif target_id == "book":
        box = (130, 125, 382, 390) if strong else (160, 145, 352, 370)
        draw.rounded_rectangle(box, radius=18, fill="#315f9d", outline="#2b2722", width=5)
        draw.line((box[0] + 65, box[1], box[0] + 65, box[3]), fill="#fffdf7", width=8)
    elif target_id == "car":
        y = 265 if strong else 285
        draw.rounded_rectangle((115, y, 397, y + 78), radius=28, fill="#d7472f", outline="#2b2722", width=5)
        draw.polygon(((190, y), (235, y - 65), (315, y - 65), (360, y)), fill="#d7472f", outline="#2b2722")
        draw.ellipse((160, y + 55, 220, y + 115), fill="#2b2722")
        draw.ellipse((292, y + 55, 352, y + 115), fill="#2b2722")
    else:
        inset = 120 if strong else 155
        draw.rectangle((inset, inset, 512 - inset, 512 - inset), outline="#2b2722", width=10)
