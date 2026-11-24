"""Debug why the cave bat swoop test fails to move the bat."""
import sys
sys.path.insert(0, ".")

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from rpg import enemies as EN
from rpg import fsm as F
from rpg.models import make_mob
from rpg.settings import load_settings
from rpg.state import GameState

gs = GameState(load_settings())
gs.select_character("knight")
gs.start_game()
gs._fsm.state = F.AREA_MOBS
px0, py0 = gs.player.x, gs.player.y
print("player at", px0, py0, "area", gs.area_id)

bat = make_mob(2, "cave_bat", gs.data["enemies"]["cave_bat"],
               px0 + 150, min(py0 + 100, gs.scene.h * gs.s.tile - 32))
print("bat spawn", bat.x, bat.y, "speed", bat.speed, "behavior", bat.behavior)
print("solid at bat?  ", gs.scene.solid(bat.x, bat.y))
gs.mobs.append(bat)
bx, by = bat.x, bat.y
EN.tick_mobs(gs, 0.016)
print("after tick", bat.x, bat.y, "delta", abs(bat.x - bx) + abs(bat.y - by))
EN.tick_mobs(gs, 0.016)
print("after tick2", bat.x, bat.y)
