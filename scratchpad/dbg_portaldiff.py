"""Diff outside render with portals vs without: which areas changed."""
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

saved = sc.interactables[:]
sc.interactables = [i for i in saved if i.kind != "portal"]
s.fill((0, 0, 0))
ui.draw_world(s, gs, am)
without_p = pygame.surfarray.array3d(s)
sc.interactables = saved

import collections
diff = (with_p != without_p).any(axis=2)
ys, xs = diff.nonzero()
if len(xs) == 0:
    print("NO DIFFERENCE: no portal drawn at all")
else:
    # cluster rough bounding boxes per 100px cell
    cells = collections.Counter(((x // 100) * 100, (y // 100) * 100)
                                for x, y in zip(xs, ys))
    print("diff pixel clusters (x,y cell):count")
    for (cx, cy), n in sorted(cells.items()):
        if n > 200:
            print(" ", cx, cy, n)
