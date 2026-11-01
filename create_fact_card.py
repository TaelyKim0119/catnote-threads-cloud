"""Render a source-checked Korean news fact card.

Usage: python create_fact_card.py spec.json output.png
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SIZE = 1080
def font_path(bold=False):
    """Use the same Korean card layout on Windows and in a Linux container."""
    candidates = (
        ["C:/Windows/Fonts/malgunbd.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]
        if bold else
        ["C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("A Korean font is required (Malgun Gothic or Noto Sans CJK)")


REGULAR = font_path()
BOLD = font_path(bold=True)
BG = "#22313D"
WHITE = "#F7F9F5"
MUTED = "#B9C3C8"
LIME = "#DDF16E"
RULE = "#34434D"
LABEL = "#8FA3AA"


def plain(value):
    return value.replace("[[", "").replace("]]", "")


def face(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def fit(draw, value, size, width, bold=True):
    while size > 28 and draw.textlength(plain(value), font=face(size, bold)) > width:
        size -= 2
    return face(size, bold)


def rich_text(draw, xy, value, font, normal=WHITE):
    x, y = xy
    for part in re.split(r"(\[\[.*?\]\])", value):
        if not part:
            continue
        accented = part.startswith("[[") and part.endswith("]]")
        segment = plain(part)
        draw.text((x, y), segment, font=font, fill=LIME if accented else normal)
        x += draw.textlength(segment, font=font)


def cat_watermark(image, stamp_name):
    """Place the supplied cat illustration as a small translucent stamp."""
    stamp_path = Path(__file__).resolve().parent / stamp_name
    stamp = Image.open(stamp_path).convert("RGBA")
    alpha = stamp.getchannel("A").point(lambda value: value if value > 12 else 0)
    stamp.putalpha(alpha)
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError(f"Empty cat stamp: {stamp_path}")
    stamp = stamp.crop(bounds)
    stamp.thumbnail((172, 172), Image.Resampling.LANCZOS)
    stamp.putalpha(stamp.getchannel("A").point(lambda value: int(value * 0.78)))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay.alpha_composite(stamp, (SIZE - 68 - stamp.width, SIZE - 49 - stamp.height))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def comic_vignette(image, asset_name):
    """Add a borderless one-panel scene below the compact fact rows."""
    asset_path = Path(__file__).resolve().parent / asset_name
    comic = Image.open(asset_path).convert("RGBA")
    alpha = comic.getchannel("A").point(lambda value: value if value > 12 else 0)
    comic.putalpha(alpha)
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError(f"Empty comic panel: {asset_path}")
    comic = comic.crop(bounds)
    comic.thumbnail((720, 270), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay.alpha_composite(comic, (SIZE - 55 - comic.width, SIZE - 28 - comic.height))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def render(spec, destination):
    image = Image.new("RGB", (SIZE, SIZE), BG)
    if spec.get("comic_panel"):
        image = comic_vignette(image, spec["comic_panel"])
    elif spec.get("cat_mark", True):
        image = cat_watermark(image, spec.get("stamp_image", "cat-stamp-mono.png"))
    draw = ImageDraw.Draw(image)

    draw.text((70, 77), spec["source"], font=face(25), fill=MUTED)
    title_font = fit(draw, max(spec["title"].splitlines(), key=lambda line: len(plain(line))), 55, 940)
    if any(draw.textlength(plain(line), font=title_font) > 940 for line in spec["title"].splitlines()):
        raise ValueError("Card title exceeds safe width")
    for i, line in enumerate(spec["title"].splitlines()):
        rich_text(draw, (67, 142 + i * 69), line, title_font)

    key_font = fit(draw, spec["highlight"], 49, 850)
    key_width = draw.textlength(plain(spec["highlight"]), font=key_font)
    if key_width > 850:
        raise ValueError("Card highlight exceeds safe width")
    draw.rounded_rectangle((68, 304, 68 + key_width + 49, 389), radius=9, fill=LIME)
    draw.text((91, 315), plain(spec["highlight"]), font=key_font, fill=BG)

    y = 427 if spec.get("comic_panel") else 450
    step = 57 if spec.get("comic_panel") else 67
    line_offset = 49 if spec.get("comic_panel") else 54
    for label, value in spec["facts"]:
        draw.text((70, y), label, font=face(26, True), fill=LABEL)
        value_font = fit(draw, value, 32, 760, bold=False)
        if draw.textlength(plain(value), font=value_font) > 760:
            raise ValueError(f"Card {label} fact exceeds safe width")
        rich_text(draw, (226, y), value, value_font)
        draw.line((68, y + line_offset, 1012, y + line_offset), fill=RULE, width=2)
        y += step

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python create_fact_card.py spec.json output.png")
    render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
