"""Audit: every door/portal must have a walkable standing tile within the
64px interact radius, reachable from spawn; print min distances."""
import sys, pathlib
from collections import deque
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpg-pygame-spade-skeleton"))
from rpg.world import outside_scene
from rpg.settings import load_settings

s = load_settings()
sc = outside_scene(40, 22, 32, (1280, 720))

def walkable(tx, ty):
    return not sc.solid(tx * 32 + 16, ty * 32 + 16)

sp = sc.spawn
src = (int(sp[0]) // 32, int(sp[1]) // 32)
dist = {src: 0}
q = deque([src])
while q:
    x, y = q.popleft()
    for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
        if (nx, ny) not in dist and walkable(nx, ny):
            dist[(nx, ny)] = dist[(x, y)] + 1
            q.append((nx, ny))

targets = {
    "lava portal      (0.5125,0.436)": (0.5125 * 1280, 0.436 * 720),
    "ice portal      (0.509,0.209) " : (0.509 * 1280, 0.209 * 720),
    "mossy portal    (0.815,0.355) ": (0.815 * 1280, 0.355 * 720),
    "void portal      (0.156,0.537)": (0.156 * 1280, 0.537 * 720),
    "outside door     (0.477,0.819)": (0.477 * 1280, 0.819 * 720),
}
ok = True
for name, (px, py) in targets.items():
    best = None
    for (tx, ty), d in dist.items():
        cx, cy = tx * 32 + 16, ty * 32 + 16
        dd = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
        if best is None or dd < best[0]:
            best = (dd, tx, ty, d)
    within = best[0] < 64
    ok &= within
    print(f"{name}: nearest standing tile ({best[1]},{best[2]}) "
          f"dist {best[0]:.0f}px {'OK - E works there' if within else 'TOO FAR - E dead zone'} "
          f"(BFS {best[3]} tiles from spawn)")
print("RESULT:", "ALL OK" if ok else "FIX NEEDED")
