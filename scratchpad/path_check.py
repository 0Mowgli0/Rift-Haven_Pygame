"""Headless checks: path map reachability, house solidness, NPC sprites."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "rpg-pygame-spade-skeleton"))
import pygame
pygame.init()
pygame.display.set_mode((1, 1))

from rpg.world import outside_scene
from rpg.assets import AssetManager
from rpg.settings import Settings

s = Settings()
s.width, s.height, s.tile = 1280, 720, 32
sc = outside_scene(40, 22, 32, (1280, 704))
W = sc.walk
T = 32
fails = []


def walkable(c, r):
    return 0 <= r < len(W) and 0 <= c < len(W[r]) and W[r][c] == "."


def tile_of(px, py):
    return int(px // T), int(py // T)


# ---- 1. BFS from spawn: every destination must be reachable --------------
from collections import deque
sp = tile_of(*sc.spawn)
seen = {sp}
q = deque([sp])
while q:
    c, r = q.popleft()
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (c + dc, r + dr)
        if n not in seen and walkable(*n):
            seen.add(n)
            q.append(n)
targets = {"lava_portal": (20, 10), "frost_portal": (20, 3),
           "mossy_portal": (31, 8), "void_portal": (6, 12),
           "house_door": (23, 21), "station_spot": (36, 19),
           "prism_egg": (14, 20), "cairn": (4, 20), "mushrooms": (13, 7),
           "sunstone_egg": (35, 12)}
for name, (c, r) in targets.items():
    ok = (c, r) in seen
    print(f"reachable {name:14s} ({c},{r}): {ok}")
    if not ok:
        fails.append(name)

# ---- 2. Walk into the house from the door path: must be blocked ----------
class Body:
    x, y = sc.spawn


b = Body()
for _ in range(4000):                       # grind up-left toward the house
    sc.move(b, -60 * 0.016, -60 * 0.25)     # steady march up and left
tc, tr = tile_of(b.x, b.y)
house_center = (19, 16)
print(f"after march: pos=({b.x:.0f},{b.y:.0f}) tile=({tc},{tr}) "
      f"walkable={walkable(tc, tr)}")
if not walkable(tc, tr):
    fails.append("player ended on a solid tile (should never happen)")
def in_house(x, y):
    """Inside the painted house footprint; the doorway strip is allowed."""
    if 730 <= x <= 800 and y > 560:
        return False  # standing at the front door is fine
    return 512 <= x <= 805 and 380 <= y <= 620


if in_house(b.x, b.y):
    fails.append("player walked onto the house")

# ---- 3. Breach attempts: march at the house from all four sides ----------
house_tiles = [(c, r) for r in range(13, 20) for c in range(16, 25)
               if not walkable(c, r)][::3]
approach = {"top": (20, 11), "bottom": (20, 20), "left": (13, 15),
            "right": (27, 15)}
for side, (ac, ar) in approach.items():
    bb = Body()
    bb.x, bb.y = ac * T + 16, ar * T + 16
    assert walkable(ac, ar), f"{side} approach not walkable"
    step = {"top": (0, 30), "bottom": (0, -30), "left": (30, 0),
            "right": (-30, 0)}[side]
    for _ in range(3):
        sc.move(bb, *step)
    bc = bb.x
    br = bb.y
    inside = in_house(bc, br)
    print(f"breach from {side:6s}: blocked={not inside}")
    if inside:
        fails.append(f"house entered from {side}")

print("RESULT:", "ALL OK" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
