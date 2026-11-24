"""Headless visual check: render home + outside scenes with real assets.

Run from rpg-pygame-spade-skeleton with SDL_VIDEODRIVER=dummy.
Writes screenshot_home.png / screenshot_outside.png next to the game.
"""

import os
import sys

import pygame

sys.path.insert(0, ".")
from rpg import ui                      # noqa: E402
from rpg import fsm as F                # noqa: E402
from rpg.assets import AssetManager     # noqa: E402
from rpg.settings import load_settings  # noqa: E402
from rpg.state import GameState         # noqa: E402

pygame.init()
screen = pygame.display.set_mode((1280, 720))
am = AssetManager(32)
gs = GameState(load_settings())
gs.select_character("knight")
gs.start_game()

world = pygame.Surface((1280, 720))
gs.area_id = "home"
ui.draw_world(world, gs, am)
pygame.image.save(world, "screenshot_home.png")

gs.area_id = "outside"
ui.draw_world(world, gs, am)
pygame.image.save(world, "screenshot_outside.png")

# END flow sanity: reach END, apply the new Esc handling exactly like main.py
gs = GameState(load_settings())
gs.select_character("knight")
gs.start_game()
gs.enter_area("green_cave")
gs.phase = F.END
assert gs._fsm.can(F.HOME) and gs._fsm.can(F.START_MENU), "END has no exits!"
# END -> HOME must not place the player inside a wall in home
gs.enter_area("home")
gs.phase = F.HOME
s = gs.scene
assert not s.solid(gs.player.x, gs.player.y), "spawn in wall"
print("VISUAL CHECK OK: home player at",
      (round(gs.player.x), round(gs.player.y)),
      "walls top solid:", all(s.grid[y][x] for x in range(40) for y in (1, 2)))
