"""Tile mosaic of the outside art: per-tile median color + tile coords.

Four quadrants saved at 2x; each cell shows the art's dominant color for that
tile so the walk map can be authored against real colors.
"""
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

mos = pygame.Surface((s.width, s.height), pygame.SRCALPHA)
font = pygame.font.SysFont(None, 18)
for ty in range(22):
    for tx in range(40):
        rs = []
        for fx in (2, 3, 4):
            for fy in (2, 3, 4):
                px = tx * t + fx * t // 6
                py = ty * t + fy * t // 6
                rs.append(tuple(int(frame[px, py, k]) for k in range(3)))
        rs.sort()
        med = rs[len(rs) // 2]
        pygame.draw.rect(mos, med, (tx * t + 2, ty * t + 2, t - 4, t - 4))
        pygame.draw.rect(mos, (255, 0, 255), (tx * t + 2, ty * t + 2,
                                              t - 4, t - 4), 1)
        lbl = font.render(f"{tx},{ty}", True, (0, 0, 0))
        mos.blit(lbl, (tx * t + 4, ty * t + 2))
del frame

mos_bg = pygame.Surface((s.width, s.height))
mos_bg.blit(bg, (0, 0))
mos_bg.blit(mos, (0, 0))
out_dir = os.path.dirname(__file__)
for name, rect in [("m_tl", (0, 0, 640, 360)), ("m_tr", (640, 0, 640, 360)),
                   ("m_bl", (0, 360, 640, 360)), ("m_br", (640, 360, 640, 360))]:
    crop = mos_bg.subsurface(pygame.Rect(rect)).copy()
    pygame.image.save(pygame.transform.scale2x(crop),
                      os.path.join(out_dir, name + ".png"))
    print("saved", name)
