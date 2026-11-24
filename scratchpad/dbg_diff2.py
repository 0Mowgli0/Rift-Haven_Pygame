"""Diff outside render with portals vs without; exact pixel extents."""
import sys
sys.path.insert(0, ".")

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from rpg import ui
from rpg.assets import AssetManager
from rpg.settings import load_settings
from rpg.state import GameState

gs = GameState(load_settings())
gs.select_character("knight")
gs.start_game()
sc = gs.scenes["outside"]
am = AssetManager(32)
s = pygame.Surface((1280, 720))
gs.area_id = "outside"

ui.draw_world(s, gs, am)
with_p = pygame.surfarray.array3d(s).copy()
print("array shape (axis0, axis1):", with_p.shape)

saved = sc.interactables[:]
sc.interactables = [i for i in saved if i.kind != "portal"]
s.fill((0, 0, 0))
ui.draw_world(s, gs, am)
without_p = pygame.surfarray.array3d(s)
sc.interactables = saved

diff = (with_p != without_p).any(axis=2)
ys, xs = diff.nonzero()
print("axis0 range", xs.min(), xs.max(), " axis1 range", ys.min(), ys.max())
