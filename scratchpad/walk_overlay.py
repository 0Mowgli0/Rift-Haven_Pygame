"""Render the outside hub walk map over the background for visual check."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "rpg-pygame-spade-skeleton"))
import pygame
from rpg.assets import AssetManager
from rpg.world import outside_scene
from rpg.settings import load_settings

s = load_settings()
pygame.init()
pygame.display.set_mode((1, 1))
surf = pygame.Surface((s.width, s.height))
am = AssetManager(s.tile)
sc = outside_scene(40, 22, s.tile, (s.width, s.height))
assert sc.walk is not None
widths = {len(r) for r in sc.walk}
print("row-count:", len(sc.walk), "row-widths:", widths)

bg = am.background("outside_hub", (s.width, s.height))
surf.blit(bg, (0, 0))
t = s.tile
chk = pygame.Surface((s.width, s.height), pygame.SRCALPHA)
for ty, row in enumerate(sc.walk):
    for tx, c in enumerate(row):
        r = pygame.Rect(tx * t, ty * t, t, t)
        if c == ".":
            pygame.draw.rect(chk, (255, 255, 0, 110), r)
surf.blit(chk, (0, 0))
for gx in range(0, s.width + 1, t):
    pygame.draw.line(surf, (255, 0, 255), (gx, 0), (gx, s.height), 1)
for gy in range(0, s.height + 1, t):
    pygame.draw.line(surf, (255, 0, 255), (0, gy), (s.width, gy), 1)
# markers: portals (from areas.json), station, door, spawn, npcs
import json
areas = json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                    "rpg-pygame-spade-skeleton",
                                    "data", "areas.json")))
for name, a in areas.items():
    fx, fy = a.get("hub_pos", (0, 0))
    x, y = round(fx * s.width), round(fy * s.height)
    pygame.draw.circle(surf, (255, 255, 0), (x + 24, y + 24), 6)
    print("portal", name, "tile", round(fx * 40), round(fy * 22))
for label, fx, fy in [("door", 0.59, 0.94), ("spawn", 0.59, 0.97),
                      ("station", 0.905, 0.85)]:
    x, y = round(fx * s.width), round(fy * s.height)
    pygame.draw.circle(surf, (0, 200, 255), (x + 16, y + 16), 6)
    print(label, "tile", round(fx * 40), round(fy * 22))
for name, x, y in [("torvald", 27, 17), ("lira", 7, 14)]:
    if name != "chef(home)":
        pygame.draw.circle(surf, (255, 0, 255), (x * t + 16, y * t + 16), 6)
        print("npc", name, "walkable:", sc.walk[y][x] == ".")
out = os.path.join(os.path.dirname(__file__), "walk_overlay.png")
pygame.image.save(surf, out)
print("saved", out)
