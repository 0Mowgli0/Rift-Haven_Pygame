"""Zoomed labeled crops of outside_hub.png (design space 1280x720, tile=32)."""
import pathlib
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1] / "rpg-pygame-spade-skeleton"
img = Image.open(ROOT / "assets/backgrounds/outside_hub.png").convert("RGB")
base = img.resize((1280, 720), Image.LANCZOS)
TILE = 32


def labeled_crop(x0, y0, x1, y1, scale, name):
    box = base.crop((x0 * TILE, y0 * TILE, x1 * TILE, y1 * TILE))
    box = box.resize((box.width * scale, box.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(box)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            px = (tx - x0) * TILE * scale
            py = (ty - y0) * TILE * scale
            d.rectangle([px, py, px + TILE * scale - 1, py + TILE * scale - 1],
                        outline=(255, 0, 255), width=1)
            d.text((px + 3, py + 3), f"{tx},{ty}", fill=(255, 255, 0))
    box.save(pathlib.Path(__file__).parent / name)
    print("wrote", name, box.size)


if __name__ == "__main__":
    labeled_crop(26, 2, 38, 14, 3, "zoom_ur.png")   # mossy ruins + stairs
    labeled_crop(8, 2, 24, 12, 3, "zoom_um.png")    # ice portal + plaza link
