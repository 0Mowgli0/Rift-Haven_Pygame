"""Scenes / tilemaps with interactables.

Each Scene is a grid of walkable floor with a wall border, named interaction
points (bed, door, station, chest, trophy cabinet, portal) and an optional
background image drawn behind everything. The interior / outside layouts are
hand-placed here; replace the grid with Tiled/CSV loading later and furniture
with data/furniture.json (TODO) — the API (solid/move/draw/nearest) stays.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import pygame


@dataclass
class Interactable:
    """An interaction point in a scene (chest, portal, station...)."""
    name: str
    kind: str  # "bed" | "door" | "station" | "chest" | "trophy" | "portal" \
               # | "exit" | "prop" (inspect text) | "food" (small heal)
    x: int      # top-left px of the interaction tile
    y: int
    data: dict = field(default_factory=dict)


class Scene:
    """A rectangular tile grid with walls, interactables and a spawn point."""

    def __init__(self, key: str, name: str, w: int, h: int, tile: int,
                 color: tuple[int, int, int],
                 bg: str | None = None,
                 painted: bool = False) -> None:
        self.key, self.name, self.tile = key, name, tile
        self.w, self.h = w, h
        self.color = color
        self.bg = bg  # background image name in assets/backgrounds/ (optional)
        # "Painted" scenes use real full-screen artwork; the drawing code then
        # trusts the picture for furniture (no placeholder sprite overlays).
        self.painted = painted
        # 1 = wall, 0 = floor. TODO: load real tilemaps.
        self.grid: list[list[int]] = [[0] * w for _ in range(h)]
        for x in range(w):
            self.grid[0][x] = self.grid[h - 1][x] = 1
        for y in range(h):
            self.grid[y][0] = self.grid[y][w - 1] = 1
        self.interactables: list[Interactable] = []
        self.spawn: tuple[float, float] | None = None  # (px, py) entry point

    def add(self, inter: Interactable) -> None:
        self.interactables.append(inter)

    def solid(self, px: float, py: float) -> bool:
        """True if the pixel position hits a wall tile."""
        tx, ty = int(px // self.tile), int(py // self.tile)
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return True
        return self.grid[ty][tx] == 1

    def move(self, obj, dx: float, dy: float) -> None:
        """Move entity by (dx, dy) respecting walls on each axis."""
        if not self.solid(obj.x + dx, obj.y):
            obj.x += dx
        if not self.solid(obj.x, obj.y + dy):
            obj.y += dy

    def free_spot(self) -> tuple[float, float]:
        """Random walkable spot away from border."""
        return (random.randint(3, self.w - 4) * self.tile,
                random.randint(3, self.h - 4) * self.tile)

    def draw(self, surface: pygame.Surface, assets) -> None:
        """Background image if set, otherwise a colored tile grid."""
        img = assets.background(self.bg, surface.get_size()) if self.bg else None
        if img is not None:
            surface.blit(img, (0, 0))
            return
        for ty in range(self.h):
            for tx in range(self.w):
                r = pygame.Rect(tx * self.tile, ty * self.tile,
                                self.tile, self.tile)
                if self.grid[ty][tx] == 1:
                    pygame.draw.rect(surface, (40, 40, 50), r)
                else:
                    base = tuple(min(255, c + ((tx + ty) % 2) * 8)
                                 for c in self.color)
                    pygame.draw.rect(surface, base, r)


def portal_locked(gs, it: Interactable) -> bool:
    """True if a hub portal is still sealed: its 'requires' boss is unbeaten."""
    conf = gs.data["areas"].get(it.data.get("area", ""), {})
    req = conf.get("requires")
    return bool(req) and req not in gs.inv.collected_bosses


def nearest_interactable(scene: Scene, px: float, py: float,
                         radius: float) -> Interactable | None:
    """Closest interactable within `radius` pixels of (px, py), else None."""
    best, bd = None, radius
    for it in scene.interactables:
        d = ((it.x - px) ** 2 + (it.y - py) ** 2) ** 0.5
        if d < bd:
            best, bd = it, d
    return best


def home_scene(w: int, h: int, tile: int,
               px: tuple[int, int] | None = None) -> Scene:
    """The house interior, matching assets/backgrounds/home_base.png.

    Interactables are placed proportionally (fractions of the picture) so they
    line up with the objects in the artwork: wardrobe, crates chest, trophy
    cabinet, gem display case, fireplace, bed, dinner table, stove and the
    front door at the bottom. The upgrade station is an overlay prop (it is
    not part of the painting). The top wall band is solid.
    """
    s = Scene("home", "Rift Haven Home", w, h, tile, (70, 90, 120),
              bg="home_base", painted=True)
    pw, ph = px or (w * tile, h * tile)

    def put(name: str, kind: str, fx: float, fy: float, **data) -> None:
        s.add(Interactable(name, kind, round(fx * pw), round(fy * ph), data))

    put("wardrobe", "prop", 0.226, 0.265,
        text="Warm cloaks and old maps of the rift scars. Nothing you need right now.")
    put("crates", "chest", 0.107, 0.46)
    put("trophy_cabinet", "trophy", 0.394, 0.26)
    put("fireplace", "prop", 0.585, 0.30,
        text="The fire crackles softly. It feels safe here.")
    put("display_case", "prop", 0.715, 0.37,
        text="Gems recovered from cleared rifts. They still shimmer.")
    put("bed", "bed", 0.93, 0.405)
    put("dinner_table", "food", 0.118, 0.73)
    put("stove", "prop", 0.875, 0.755,
        text="A pot of stew simmers on the stove.")
    s.add(Interactable("upgrade_station", "station",
                       round(0.645 * pw), round(0.66 * ph)))
    put("front_door", "door", 0.485, 0.955)
    # The painted wall band across the top of home_base.png is solid; the
    # bottom border is opened because the picture's doorway sits at the very
    # bottom edge (solid() still pins the player at the 704px grid end).
    for y in (1, 2, 3):
        s.grid[y] = [1] * w
    s.grid[h - 1] = [0] * w
    s.spawn = (round(0.485 * pw), round(0.87 * ph))
    return s


def outside_scene(w: int, h: int, tile: int,
                  px: tuple[int, int] | None = None) -> Scene:
    """Outside the house, matching assets/backgrounds/outside_hub.png.

    The hub stays data-driven: one portal interactable per area from
    data/areas.json is added by GameState (see _add_hub_portals), each pinned
    to its picture portal via the area's "hub_pos" fraction. The house door
    leads back inside; eggs/mushrooms/stone pile are inspectable props.
    Spawn is on the path just below the house door.
    """
    s = Scene("outside", "Haven Outside", w, h, tile, (70, 110, 70),
              bg="outside_hub", painted=True)
    pw, ph = px or (w * tile, h * tile)

    def put(name: str, kind: str, fx: float, fy: float, **data) -> None:
        s.add(Interactable(name, kind, round(fx * pw), round(fy * ph), data))

    s.add(Interactable("house_door", "door",
                       round(0.59 * pw), round(0.94 * ph)))
    put("prism_egg", "prop", 0.359, 0.879,
        text="A prismatic egg hums with rift energy. Best leave it be... for now.")
    put("sunstone_egg", "prop", 0.902, 0.552,
        text="An egg of living light. It is warm, like a small sun.")
    put("mushroom_ring", "prop", 0.336, 0.292,
        text="Glowshrooms. Hunters say they sprout where rifts will open.")
    put("stone_cairn", "prop", 0.117, 0.93,
        text="A traveller's cairn. Someone made it home safely once.")
    # The painted treeline across the top is solid; bottom border opened for
    # the house-door approach at the bottom edge.
    for y in (1, 2):
        s.grid[y] = [1] * w
    s.grid[h - 1] = [0] * w
    s.spawn = (round(0.59 * pw), round(0.97 * ph))
    return s


def area_scene(key: str, name: str, w: int, h: int, tile: int,
               color: tuple[int, int, int],
               bg: str | None = None) -> Scene:
    """An explorable area; the return portal back home is at the entrance."""
    s = Scene(key, name, w, h, tile, color, bg=bg)
    s.add(Interactable("exit_home", "exit", 2 * tile, 2 * tile,
                       {"area": "home"}))
    return s
