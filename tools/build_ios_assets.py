from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
APP_ICON_SOURCE = ROOT / "web" / "public" / "brand" / "gitai-app-icon-source.png"
APP_ICON_TARGET = ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-512@2x.png"
SPLASH_DIR = ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "Splash.imageset"
FONT_CANDIDATES = (
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build iOS app icon and splash assets.")
    parser.parse_args()
    build_ios_assets()
    print(f"Wrote {APP_ICON_TARGET}")
    print(f"Wrote splash assets to {SPLASH_DIR}")


def build_ios_assets() -> None:
    if not APP_ICON_SOURCE.exists():
        raise SystemExit(f"Missing app icon source: {APP_ICON_SOURCE}")
    APP_ICON_TARGET.parent.mkdir(parents=True, exist_ok=True)
    icon = Image.open(APP_ICON_SOURCE).convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.save(APP_ICON_TARGET)

    splash = render_splash()
    SPLASH_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ("splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"):
        splash.save(SPLASH_DIR / filename)


def render_splash() -> Image.Image:
    image = Image.new("RGB", (2732, 2732), "#244f43")
    draw = ImageDraw.Draw(image)
    icon = Image.open(APP_ICON_SOURCE).convert("RGBA").resize((760, 760), Image.Resampling.LANCZOS)
    image.paste(icon.convert("RGB"), ((2732 - 760) // 2, 850), icon.split()[-1])
    title_font = font(156)
    sub_font = font(52)
    title = "gitai"
    sub = "AIをだます擬態ドローイング"
    draw_center(draw, title, title_font, 1660, "#fffaf0")
    draw_center(draw, sub, sub_font, 1840, "#e7c24e")
    return image


def draw_center(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.FreeTypeFont, y: int, color: str) -> None:
    width = draw.textlength(text, font=font_obj)
    draw.text(((2732 - width) / 2, y), text, font=font_obj, fill=color)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        candidate = Path(path)
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


if __name__ == "__main__":
    main()
