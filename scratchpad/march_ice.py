"""March test with the real Scene.move mechanics: pocket -> frost portal."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "rpg-pygame-spade-skeleton"))

from rpg.world import outside_scene
from rpg.settings import load_settings

s = load_settings()
sc = outside_scene(40, 22, 32, (1280, 720))

class P:
    x, y = 24 * 32 + 16, 10 * 32 + 14  # robot position from screenshot

p = P()

def step_towards(tx, ty):
    """One 4px step toward tile target using Scene.move axis logic."""
    gx, gy = tx * 32 + 16, ty * 32 + 16
    dx = max(-4, min(4, gx - p.x))
    dy = max(-4, min(4, gy - p.y))
    sc.move(p, dx, dy)
    return abs(p.x - gx) < 6 and abs(p.y - gy) < 6

# Waypoint route discoverable by BFS on tiles first.
from collections import deque
def bfs(src, dst):
    q, seen, par = deque([src]), {src}, {}
    while q:
        c = q.popleft()
        if c == dst:
            path = [c]
            while c in par:
                c = par[c]
                path.append(c)
            return path[::-1]
        x, y = c
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if (nx, ny) not in seen and not sc.solid(nx*32+16, ny*32+16):
                seen.add((nx, ny)); par[(nx, ny)] = c; q.append((nx, ny))
    return None

start = (p.x // 32, p.y // 32)
for goal in [(20, 5), (20, 4), (19, 6), (31, 8)]:
    path = bfs(start, goal)
    print(f"BFS {start} -> {goal}: {'OK ' + str(len(path)) + ' tiles' if path else 'UNREACHABLE'}")
    if path:
        p.x, p.y = 24 * 32 + 16, 10 * 32 + 14
        ok = True
        for t in path:
            while not step_towards(*t):
                pass
        dist_blocked = sc.solid(p.x, p.y)
        print(f"  marched to ({p.x:.0f},{p.y:.0f}) tile ({p.x//32},{p.y//32}) ended_on_walkable={not dist_blocked}")
