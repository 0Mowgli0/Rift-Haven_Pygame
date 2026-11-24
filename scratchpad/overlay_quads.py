"""Zoomed quadrants of the walk overlay for tile-by-tile map authoring."""
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
t = s.tile
sc = outside_scene(40, 22, t, (s.width, s.height))
walk = sc.walk

bg = am.background("outside_hub", (s.width, s.height))
surf.blit(bg, (0, 0))
chk = pygame.Surface((s.width, s.height), pygame.SRCALPHA)
font = pygame.font.SysFont(None, 18)
for ty, row in enumerate(walk):
    for tx, c in enumerate(row):
        r = pygame.Rect(tx * t, ty * t, t, t)
        if c == ".":
            pygame.draw.rect(chk, (40, 120, 255, 150), r)
surf.blit(chk, (0, 0))
# coordinates every tile at edges + crosshair dots at tile corners
for tx in range(40):
    pygame.display.set_mode((1, 1))
    for ty in range(22):
        if tx % 2 == 0 and ty % 2 == 0:
            lbl = font.render(f"{tx},{ty}", True, (255, 0, 255))
            surf.blit(lbl, (tx * t + 1, ty * t + 1))
for gx in range(0, s.width + 1, t):
    pygame.draw.line(surf, (255, 0, 255, 0), (gx, 0), (gx, s.height), 1)
for gy in range(0, s.height + 1, t):
    pygame.draw.line(surf, (255, 0, 255, 0), (0, gy), (s.width, gy), 1)

out_dir = os.path.dirname(__file__)
for name, rect in [("q_tl", (0, 0, 640, 360)), ("q_tr", (640, 0, 640, 360)),
                   ("q_bl", (0, 360, 640, 360)), ("q_br", (640, 360, 640, 360))]:
    crop = surf.subsurface(pygame.Rect(rect)).copy()
    crop = pygame.transform.scale2x(crop)
    p = os.path.join(out_dir, name + ".png")
    pygame.image.save(crop, p)
    print("saved", p)
