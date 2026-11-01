"""Compose a quiet, borderless one-panel cat vignette without text or numbers."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent
INK = "#946C71"
CREAM = "#F1E9DA"
PINK = "#C98491"
BLUE = "#8B9BA8"
LINE = 5


def scene(prop: str, output: Path) -> None:
    image = Image.new("RGBA", (760, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if prop == "screen":
        draw.rounded_rectangle((65, 46, 385, 226), radius=12, fill=CREAM, outline=INK, width=LINE)
        draw.line((70, 92, 380, 92), fill=INK, width=3)
        for x in (87, 110, 133):
            draw.ellipse((x, 68, x + 9, 77), fill=PINK)
        draw.rounded_rectangle((95, 118, 210, 190), radius=8, outline=BLUE, width=4)
        draw.line((230, 129, 340, 129), fill=BLUE, width=5)
        draw.line((230, 158, 320, 158), fill=BLUE, width=5)
        draw.line((230, 187, 352, 187), fill=BLUE, width=5)
    elif prop == "chip":
        draw.rounded_rectangle((125, 58, 327, 247), radius=16, fill=CREAM, outline=INK, width=LINE)
        draw.rounded_rectangle((164, 97, 289, 209), radius=9, fill=BLUE, outline=INK, width=4)
        for x in (153, 204, 255, 306):
            draw.line((x, 40, x, 57), fill=PINK, width=7)
            draw.line((x, 248, x, 265), fill=PINK, width=7)
        for y in (84, 132, 180, 228):
            draw.line((108, y, 124, y), fill=PINK, width=7)
            draw.line((328, y, 345, y), fill=PINK, width=7)
    elif prop == "phone":
        draw.rounded_rectangle((142, 24, 324, 274), radius=25, fill=CREAM, outline=INK, width=LINE)
        draw.rounded_rectangle((161, 60, 305, 227), radius=9, fill=BLUE)
        draw.line((214, 245, 250, 245), fill=INK, width=5)
        draw.ellipse((201, 110, 266, 175), fill=PINK)
    elif prop == "robot":
        draw.rounded_rectangle((100, 81, 350, 236), radius=35, fill=CREAM, outline=INK, width=LINE)
        draw.ellipse((153, 133, 180, 160), fill=PINK)
        draw.ellipse((267, 133, 294, 160), fill=PINK)
        draw.arc((190, 146, 255, 202), 10, 170, fill=INK, width=4)
        draw.line((225, 77, 225, 46), fill=INK, width=5)
        draw.ellipse((214, 34, 236, 56), fill=PINK, outline=INK, width=3)
    elif prop == "lock":
        draw.arc((139, 18, 317, 183), 180, 360, fill=INK, width=12)
        draw.rounded_rectangle((116, 120, 341, 261), radius=18, fill=CREAM, outline=INK, width=LINE)
        draw.ellipse((212, 166, 245, 199), fill=PINK)
        draw.line((229, 195, 229, 222), fill=INK, width=5)
    elif prop == "globe":
        draw.ellipse((103, 27, 360, 277), fill=CREAM, outline=INK, width=LINE)
        draw.arc((164, 31, 298, 275), 70, 290, fill=BLUE, width=4)
        draw.arc((164, 31, 298, 275), 250, 470, fill=BLUE, width=4)
        draw.line((109, 151, 355, 151), fill=BLUE, width=4)
        draw.arc((107, 91, 357, 210), 10, 170, fill=PINK, width=5)
    elif prop == "satellite":
        draw.rounded_rectangle((177, 109, 270, 191), radius=12, fill=CREAM, outline=INK, width=LINE)
        for x in (64, 278):
            draw.polygon([(x, 87), (x + 91, 99), (x + 91, 201), (x, 212)], fill=BLUE, outline=INK)
            for y in (122, 162):
                draw.line((x + 8, y, x + 84, y), fill=CREAM, width=3)
        draw.arc((138, 104, 179, 196), 70, 290, fill=PINK, width=5)
        draw.arc((273, 112, 324, 187), 255, 465, fill=PINK, width=5)
    else:  # document
        draw.polygon([(107, 31), (316, 31), (356, 71), (356, 263), (107, 263)], fill=CREAM)
        draw.line((107, 31, 316, 31, 356, 71, 356, 263, 107, 263, 107, 31), fill=INK, width=LINE)
        draw.line((315, 33, 315, 72, 353, 72), fill=INK, width=4)
        for y, length in ((111, 160), (148, 188), (185, 139), (222, 174)):
            draw.line((139, y, 139 + length, y), fill=BLUE, width=5)

    # Shared motion cue joins the article prop to the cat without implying data.
    draw.arc((320, 75, 520, 235), 230, 320, fill=PINK, width=5)
    draw.line((390, 52, 409, 32), fill=PINK, width=5)
    draw.line((411, 65, 438, 55), fill=PINK, width=5)

    cat = Image.open(ROOT / "cat-hop.png").convert("RGBA")
    alpha = cat.getchannel("A").point(lambda value: 0 if value < 24 else value)
    cat.putalpha(alpha)
    bounds = alpha.getbbox()
    if not bounds:
        raise ValueError("Cat cutout has no alpha")
    cat = cat.crop(bounds)
    cat.thumbnail((405, 265), Image.Resampling.LANCZOS)
    image.alpha_composite(cat, (342, 20))
    # Calm the whole vignette without changing the established brand palette.
    alpha = image.getchannel("A")
    toned = ImageEnhance.Color(image.convert("RGB")).enhance(0.70)
    toned = ImageEnhance.Brightness(toned).enhance(0.79)
    image = toned.convert("RGBA")
    image.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
