"""Draw one real frame of the outside hub + home to verify NPC sprites."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "rpg-pygame-spade-skeleton"))
import pygame
pygame.init()
screen = pygame.display.set_mode((1280, 720))

from rpg.assets import AssetManager
from rpg import ui
from rpg.state import GameState
from rpg.settings import load_settings

s = load_settings()
am = AssetManager(s.tile)
gs = GameState(s)
gs.select_character("knight")
gs.start_game()
out = os.path.join(os.path.dirname(__file__), "frame_outside.png")
try:
    gs.enter_area("outside")
    ui.draw_world(screen, gs, am)
    # draw the NPCs' E-prompts too by proximity trick: teleport player near Lira
    for npc_x, npc_y, tag in ((35, 19, "torvald"), (5, 12, "lira")):
        pass
    pygame.image.save(screen, out)
    print("saved outside frame")

    # sprite presence check
    for n in gs.npcs:
        if n["scene"] == gs.area_id:
            from pathlib import Path
            p = Path("assets/npcs") / n["sprite"]
            print(n["name"], n["sprite"], "exists:", p.exists(),
                  "walkable:", gs.scene.walk[n["y"]][n["x"]] == ".")
finally:
    gs.enter_area("home")
    ui.draw_world(screen, gs, am)
    # put player near chef and redraw so we see the prompt region
    for n in gs.npcs:
        if n["scene"] == "home" and n["id"] == "chef":
            gs.player.x, gs.player.y = (n["x"] + 2) * 32, (n["y"] + 1) * 32
    ui.draw_world(screen, gs, am)
    out2 = os.path.join(os.path.dirname(__file__), "frame_home.png")
    pygame.image.save(screen, out2)
    print("saved home frame")
