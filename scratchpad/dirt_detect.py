"""Classify each hub tile as dirt-path (walkable) or other (solid) by color."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "rpg-pygame-spade-skeleton"))
import pygame
from rpg.assets import AssetManager
from rpg.settings import load_settings

s = load_settings()
pygame.init()
pygame.display.set_mode((1, 1))
surf = pygame.Surface((s.width, s.height))
am = AssetManager(s.tile)
t = s.tile
bg = am.background("outside_hub", (s.width, s.height))
surf.blit(bg, (0, 0))
frame = pygame.surfarray.pixels3d(surf)  # [x][y][rgb]

rows = []
for ty in range(22):
    row = ""
    for tx in range(40):
        # sample a 5x5 grid of points inside the tile, skip 2px border
        votes = n = 0
        for fx in range(1, 6):
            for fy in range(1, 6):
                px = tx * t + int(fx * t / 6)
                py = ty * t + int(fy * t / 6)
                r, g, b = (int(frame[px, py, k]) / 255 for k in range(3))
                mx, mn = max(r, g, b), min(r, g, b)
                sat = 0 if mx == 0 else (mx - mn) / mx
                if mx == r:
                    hue = 60 * ((g - b) / (mx - mn) if mx - mn else 0) % 360
                else:
                    hue = 999  # not red-dominant -> definitely not dirt
                dirt = sat > 0.25 and mx > 0.25 and 15 <= hue <= 50
                votes += 1 if dirt else 0
                n += 1
        row += "." if votes / n >= 0.35 else "#"
    rows.append(row)
del frame

for ty, r in enumerate(rows):
    print(f"{ty:2d} {r}  len={len(r)}")

out = os.path.join(os.path.dirname(__file__), "dirt_overlay.png")
chk = pygame.Surface((s.width, s.height), pygame.SRCALPHA)
for ty, r in enumerate(rows):
    for tx, c in enumerate(r):
        if c == ".":
            pygame.draw.rect(chk, (40, 120, 255, 150),
                             (tx * t, ty * t, t, t))
surf.blit(chk, (0, 0))
pygame.image.save(surf, out)
print("saved", out)
