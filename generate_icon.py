#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSET_DIR = "Sources/SubtitleDownloaderGUI/Resources/Assets.xcassets/AppIcon.appiconset"
SIZES = [
    (16, [1, 2]),
    (32, [1, 2]),
    (128, [1, 2]),
    (256, [1, 2]),
    (512, [1, 2]),
]

def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def create_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    padding = int(size * 0.08)
    corner_radius = int(size * 0.22)

    # Gradient background (blue -> cyan)
    for y in range(size):
        ratio = y / size
        r = int(45 + (80 - 45) * ratio)
        g = int(120 + (180 - 120) * ratio)
        b = int(220 + (255 - 220) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Inner rounded rectangle (slightly lighter)
    inner_pad = padding
    draw.rounded_rectangle(
        [inner_pad, inner_pad, size - inner_pad, size - inner_pad],
        radius=corner_radius - inner_pad,
        fill=(255, 255, 255, 35)
    )

    # Film strip / subtitle card
    card_margin = int(size * 0.22)
    card_top = int(size * 0.24)
    card_bottom = int(size * 0.62)
    card_radius = int(size * 0.06)
    draw.rounded_rectangle(
        [card_margin, card_top, size - card_margin, card_bottom],
        radius=card_radius,
        fill=(255, 255, 255, 230)
    )

    # Film strip sprocket holes
    hole_w = int(size * 0.04)
    hole_h = int(size * 0.03)
    hole_y_top = card_top + int((card_bottom - card_top) * 0.15)
    hole_y_bottom = card_bottom - int((card_bottom - card_top) * 0.15)
    hole_count = 4
    for i in range(hole_count):
        x = int(card_margin + (size - 2 * card_margin) * (i + 1) / (hole_count + 1))
        draw.rounded_rectangle(
            [x - hole_w // 2, hole_y_top - hole_h // 2, x + hole_w // 2, hole_y_top + hole_h // 2],
            radius=2,
            fill=(30, 40, 60, 200)
        )
        draw.rounded_rectangle(
            [x - hole_w // 2, hole_y_bottom - hole_h // 2, x + hole_w // 2, hole_y_bottom + hole_h // 2],
            radius=2,
            fill=(30, 40, 60, 200)
        )

    # Subtitle lines
    line_color = (40, 50, 70, 220)
    line_w = int(size * 0.34)
    line_h = max(2, int(size * 0.028))
    line_y1 = int(size * 0.70)
    line_y2 = line_y1 + int(size * 0.09)
    cx = size // 2
    draw.rounded_rectangle([cx - line_w // 2, line_y1, cx + line_w // 2, line_y1 + line_h], radius=line_h // 2, fill=line_color)
    draw.rounded_rectangle([cx - line_w // 2, line_y2, cx + line_w // 2, line_y2 + line_h], radius=line_h // 2, fill=line_color)

    # Optional: small sparkle/star accent
    star_color = (255, 220, 80, 230)
    star_size = int(size * 0.06)
    star_x = int(size * 0.78)
    star_y = int(size * 0.20)
    draw.polygon([
        (star_x, star_y - star_size),
        (star_x + star_size // 3, star_y - star_size // 3),
        (star_x + star_size, star_y),
        (star_x + star_size // 3, star_y + star_size // 3),
        (star_x, star_y + star_size),
        (star_x - star_size // 3, star_y + star_size // 3),
        (star_x - star_size, star_y),
        (star_x - star_size // 3, star_y - star_size // 3),
    ], fill=star_color)

    # Shadow / glossy overlay for depth
    overlay = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.ellipse([size * 0.2, -size * 0.3, size * 0.8, size * 0.4], fill=(255, 255, 255, 30))
    img = Image.alpha_composite(img, overlay)

    return img

if __name__ == "__main__":
    os.makedirs(ASSET_DIR, exist_ok=True)
    # Generate 1024x1024 master
    master = create_icon(1024)
    master.save(os.path.join(ASSET_DIR, "icon_1024x1024.png"))

    for base, scales in SIZES:
        for scale in scales:
            px = base * scale
            img = create_icon(px)
            if scale == 1:
                name = f"icon_{base}x{base}.png"
            else:
                name = f"icon_{base}x{base}@{scale}x.png"
            img.save(os.path.join(ASSET_DIR, name))
            print(f"Generated {name} ({px}x{px})")

    print("Done.")
