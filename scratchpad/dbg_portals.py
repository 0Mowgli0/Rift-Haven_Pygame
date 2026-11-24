"""Check portal draw gating on painted scenes + dump key colors."""
import sys
sys.path.insert(0, ".")

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from rpg import ui
from rpg.assets import AssetManager
from rpg.settings import load_settings
from rpg.state import GameState
from rpg.world import portal_locked, nearest_interactable

gs = GameState(load_settings())
gs.select_character("knight")
gs.start_game()
sc = gs.scenes["outside"]
print("painted:", sc.painted)
for it in sc.interactables:
    if it.kind == "portal":
        print(it.name, it.data["area"], (it.x, it.y),
              "locked:", portal_locked(gs, it))

am = AssetManager(32)
s = pygame.Surface((1280, 720))
gs.area_id = "outside"
gs.player.x, gs.player.y = sc.spawn
ui.draw_world(s, gs, am)

# Fire portal (green_cave, unlocked) -> background art, no procedural swirl.
fire = next(i for i in sc.interactables if i.kind == "portal"
            and i.data["area"] == "green_cave")
print("pixel at fire portal center:", s.get_at((fire.x + 16, fire.y + 16)))

# Prompt/E-range sanity at the fire portal and house door.
door = next(i for i in sc.interactables if i.kind == "door")
print("door prompt in range from spawn:",
      nearest_interactable(sc, *sc.spawn, 64) is not None)
