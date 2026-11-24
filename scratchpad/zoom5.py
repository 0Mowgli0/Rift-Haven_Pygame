import pathlib
from art_zoom2 import TILE, base, ImageDraw
from PIL import Image

def crop_frac(x0, y0, x1, y1, frac_x, frac_y, scale, name, src=None):
    """crop of design-space box with px grid; draws dot at (fx,fy) fractions."""
    img = base if src is None else src
    box = img.crop((x0, y0, x1, y1))
    box = box.resize((box.width * scale, box.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(box)
    px = (frac_x * 1280 - x0) * scale
    py = (frac_y * 720 - y0) * scale
    d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(255, 0, 0))
    for gx in range(0, box.width, TILE * scale):
        d.rectangle([gx, 0, gx + 1, box.height], outline=(255, 0, 255))
        d.text((gx + 3, 3), str((gx / scale + x0) // TILE), fill=(255, 255, 0))
    for gy in range(0, box.height, TILE * scale):
        d.rectangle([0, gy, box.width, gy + 1], outline=(255, 0, 255))
        d.text((3, gy + 3), str((gy / scale + y0) // TILE), fill=(255, 255, 0))
    box.save(pathlib.Path(__file__).parent / name)
    print("wrote", name)

home = Image.open(
    pathlib.Path(__file__).resolve().parents[1] / "rpg-pygame-spade-skeleton/assets/backgrounds/home_base.png"
).convert("RGB").resize((1280, 720), Image.LANCZOS)

# outside house + door area, mark current door interact (0.59, 0.94)
crop_frac(18 * TILE, 13 * TILE, 28 * TILE, 22 * TILE, 0.59, 0.94, 3,
          "zoom_house_door.png")
# home interior bottom, mark current front door (0.485, 0.955)
crop_frac(12 * TILE, 15 * TILE, 28 * TILE, 22 * TILE, 0.485, 0.955, 3,
          "zoom_home_door.png", src=home)
