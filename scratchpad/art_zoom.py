"""2x zoom crops of specific regions of the raw outside art."""
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
font = pygame.font.SysFont(None, 20)
for ty in range(22):
    for tx in range(40):
        lbl = font.render(f"{tx},{ty}", True, (255, 0, 255))
        surf.blit(lbl, (tx * t + 2, ty * t + 2))
for gx in range(0, s.width + 1, t):
    pygame.draw.line(surf, (255, 0, 255), (gx, 0), (gx, s.height), 1)
for gy in range(0, s.height + 1, t):
    pygame.draw.line(surf, (255, 0, 255), (0, gy), (s.width, gy), 1)

out_dir = os.path.dirname(__file__)
for name, rect in [("z_door", (20 * t, 10 * t, 10 * t, 8 * t)),
                   ("z_station", (24 * t, 14 * t, 12 * t, 8 * t)),
                   ("z_left", (0, 10 * t, 12 * t, 10 * t))]:
    crop = surf.subsurface(pygame.Rect(rect)).copy()
    crop = pygame.transform.smoothscale(
        crop, (rect[2] * 2, rect[3] * 2))
    pygame.image.save(crop, os.path.join(out_dir, name + ".png"))
    print("saved", name)
