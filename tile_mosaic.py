"""Zoomed labeled crops of outside_hub.png regions + per-tile median colors.

Usage: writes zoom_left.png / zoom_right.png (2x, 32px-tile gridlines, tile
coords labeled) and prints median tile colors for regions of interest.
"""
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1] / "rpg-pygame-spade-skeleton"
img = Image.open(ROOT / "assets/backgrounds/outside_hub.png").convert("RGB")
# Background is drawn scaled to full window; native bigger. Design space:
# 40x22 tiles over 1280x720, so tile in design px = 32. Scale art to that.
base = img.resize((1280, 720), Image.LANCZOS)
TILE = 32

FONT = None
try:
    from PIL import ImageDraw
    FONT = ImageDraw.Draw
except ImportError:
    raise SystemExit("PIL ImageDraw missing")


def labeled_crop(x0, y0, x1, y1, scale, name):
    # tiles inclusive, coords in design pixels
    box = base.crop((x0 * TILE, y0 * TILE, x1 * TILE, y1 * TILE))
    box = box.resize((box.width * scale, box.height * scale), Image.NEAREST)
    d = FONT(box)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            px = (tx - x0) * TILE * scale
            py = (ty - y0) * TILE * scale
            d.rectangle([px, py, px + TILE * scale - 1, py + TILE * scale - 1],
                        outline=(255, 0, 255), width=1)
            if scale >= 2:
                d.text((px + 3, py + 3), f"{tx},{ty}", fill=(255, 255, 0))
    box.save(pathlib.Path(__file__).parent / name)
    print("wrote", name, box.size)


def med(x0, y0, x1, y1):
    import statistics
    px = base.crop((x0 * TILE, y0 * TILE, (x1 + 1) * TILE, (y1 + 1) * TILE))
    cols = list(px.getdata())
    r = statistics.median(c[0] for c in cols)
    g = statistics.median(c[1] for c in cols)
    b = statistics.median(c[2] for c in cols)
    return (int(r), int(g), int(b))


# Upper-right: mossy ruins / green portal / stairs to road
labeled_crop(24, 2, 38, 12, 3, "zoom_ur.png")
# Upper-middle: ice portal plateau + connector toward plaza / lava rock
labeled_crop(8, 2, 25, 12, 3, "zoom_um.png")

if __name__ == "__main__":
    pass
