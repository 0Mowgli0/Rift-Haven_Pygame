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
        # Optional painted-path map ('.' = walkable, '#' = solid) laid over
        # the artwork; when set it replaces the grid for movement checks so
        # the player stays on the drawn paths (see _HUB_PATH below).
        self.walk: list[str] | None = None
        self.interactables: list[Interactable] = []
        self.spawn: tuple[float, float] | None = None  # (px, py) entry point

    def add(self, inter: Interactable) -> None:
        self.interactables.append(inter)

    def solid(self, px: float, py: float) -> bool:
        """True if the pixel position hits a wall (or off the painted path)."""
        tx, ty = int(px // self.tile), int(py // self.tile)
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return True
        if self.walk is not None:
            if ty >= len(self.walk) or tx >= len(self.walk[ty]):
                return True
            return self.walk[ty][tx] != "."
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
    front door at the bottom. The upgrade station lives outside now (see
    outside_scene). The top wall band is solid.
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
    put("front_door", "door", 0.485, 0.955)
    # The painted wall band across the top of home_base.png is solid; the
    # bottom border is opened because the picture's doorway sits at the very
    # bottom edge (solid() still pins the player at the 704px grid end).
    for y in (1, 2, 3):
        s.grid[y] = [1] * w
    s.grid[h - 1] = [0] * w
    s.spawn = (round(0.485 * pw), round(0.87 * ph))
    return s


# Walkable-path map for the painted outside hub (matches
# assets/backgrounds/outside_hub.png). 40 tiles x 22 tiles; '.' = path you can
# walk, '#' = the house footprint, treeline, hedges and grass (solid). Row 0-1
# and the outer ring are art/tree bands. The corridors follow the dirt path:
# top-left entrance, frost-portal spur, central plaza around the lava rift,
# spur to the mossy ruins, the void-rift approach on the left, the bottom-left
# passage by the cairn, the door steps below the house and the bottom-right
# corridor out past the smithy corner.
_HUB_PATH = [
    "########################################",
    "#######....#############################",
    "#######....#.....#######################",
    "#######..................###############",
    "########.................###############",
    "########.................###############",
    "#######..................####..####..###",
    "#######............#####.......####..###",
    "########..........######............####",
    "########..........######............####",
    "########............................####",
    "##...............##.................####",
    "##..............##########...........###",
    "##............############..........####",
    "##............############..........####",
    "##............############.........#####",
    "##............############.........#####",
    "##............############.........#####",
    "##............############............##",
    "##....................................##",
    "##...........................#........##",
    "##...........................####.....##",
]


def outside_scene(w: int, h: int, tile: int,
                  px: tuple[int, int] | None = None) -> Scene:
    """Outside the house, matching assets/backgrounds/outside_hub.png.

    The hub stays data-driven: one portal interactable per area from
    data/areas.json is added by GameState (see _add_hub_portals), each pinned
    to its picture portal via the area's "hub_pos" fraction. The house door
    leads back inside; the bottom-right smithy corner holds the upgrade
    station (with Smith Torvald beside it); eggs/mushrooms/stone pile are
    inspectable props.
    Spawn is on the path just below the house door.
    """
    s = Scene("outside", "Haven Outside", w, h, tile, (70, 110, 70),
              bg="outside_hub", painted=True)
    pw, ph = px or (w * tile, h * tile)

    def put(name: str, kind: str, fx: float, fy: float, **data) -> None:
        s.add(Interactable(name, kind, round(fx * pw), round(fy * ph), data))

    # Door point sits on the painted doorway (tiles ~18.5-20, rows 17-20);
    # the player walks up the steps and presses E right at the door.
    s.add(Interactable("house_door", "door",
                       round(0.477 * pw), round(0.819 * ph)))
    # Top-left stone path (tiles ~7-10) leads up out of the hub to the town.
    s.add(Interactable("town_path", "door",
                       round(0.225 * pw), round(0.068 * ph),
                       {"to": "town"}))
    put("prism_egg", "prop", 0.359, 0.879,
        text="A prismatic egg hums with rift energy. Best leave it be... for now.")
    put("sunstone_egg", "prop", 0.902, 0.552,
        text="An egg of living light. It is warm, like a small sun.")
    put("mushroom_ring", "prop", 0.336, 0.292,
        text="Glowshrooms. Hunters say they sprout where rifts will open.")
    put("stone_cairn", "prop", 0.117, 0.93,
        text="A traveller's cairn. Someone made it home safely once.")
    # Smithy corner (bottom-right): the upgrade station with Torvald beside it.
    s.add(Interactable("upgrade_station", "station",
                       round(0.905 * pw), round(0.85 * ph)))
    # The painted treeline across the top is solid; bottom border opened for
    # the house-door approach at the bottom edge.
    for y in (1, 2):
        s.grid[y] = [1] * w
    s.grid[h - 1] = [0] * w
    # The player may only walk the dirt path drawn in the picture (see
    # _HUB_PATH): the house, treeline and hedges are all solid.
    s.walk = _HUB_PATH
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


# ---------------------------------------------------------------------------
# The town (mainTown.png) and its shops. Same 40x22 design grid as the hub:
# '.' = walkable, '#' = buildings / fences / furniture painted in the art.
# Doors and gates are hotspots the player reaches on the walkable side.
_TOWN_PATH = [
    "########################################",
    "##############...........############..#",
    "##############...........############..#",
    "################.........###############",
    "################.........###############",
    "#...############.........###############",
    "##########..####.........#####...#######",
    "##########..####.........#####...#######",
    "##########..####.........#####...#######",
    "########....####.......................#",
    "########.##............................#",
    "########.##............................#",
    "####..##.##..###########..#............#",
    "####..##.##..#........#####..####......#",
    "####..##.....#........###########......#",
    "#............#........###########......#",
    "#............#..####..#####..####......#",
    "#............#..####..#...#............#",
    "#...###.....#########.#...#............#",
    "#...###.....####.......................#",
    "#######.....####..........###########..#",
    "########################################",
]


def town_scene(w: int, h: int, tile: int,
               px: tuple[int, int] | None = None) -> Scene:
    """The town square, matching assets/backgrounds/mainTown.png.

    Three shop buildings (potion top-left, weapons left, stonemason top
    right) entered with E at their doors; a stone path up top leads to the
    realm "Rifts & Beyond" sign, the garden fence gate opens onto "The
    Magical Gardens", and the road out the bottom returns to the outside hub.
    The fountain, buildings, trees and fences are solid.
    """
    s = Scene("town", "Rift Haven Town", w, h, tile, (110, 100, 90),
              bg="mainTown", painted=True)

    def put(name: str, kind: str, tx: float, ty: float, **data) -> None:
        s.add(Interactable(name, kind, round(tx * tile), round(ty * tile),
                           data))

    put("shop_potion_door", "door", 10.5, 7.5, to="shop_potion",
        prompt="Enter shop")
    put("shop_weapon_door", "door", 4.8, 13.5, to="shop_weapon",
        prompt="Enter shop")
    put("shop_stone_door", "door", 31.2, 7.5, to="shop_stone",
        prompt="Enter townhall")
    put("beyond_sign", "gate", 22.5, 5.0, to="beyond",
        label="Rifts & Beyond")
    put("gardens_gate", "gate", 24.3, 17.8, to="gardens",
        label="The Magical Gardens")
    put("fountain", "prop", 29.4, 13.3,
        text="Clear water whispers over old stone. You feel steadier somehow.")
    put("to_outside", "door", 8.5, 21.0, to="outside")
    s.walk = _TOWN_PATH
    # Arrive in front of the townhall instead of at the far edge of town.
    s.spawn = (round(31.2 * tile), round(9.4 * tile))
    return s


def store_scene(key: str, name: str, bg: str, color: tuple[int, int, int],
                walk: list[str], w: int, h: int, tile: int,
                door_tx: float, door_ty: float, spawn: tuple[float, float],
                props: list[dict] | None = None, px: tuple[int, int] | None = None
                ) -> Scene:
    """A painted shop interior: walls/counters solid, one door back to town.

    `walk` is a 40x22 '.'/'#' map laid over the artwork; the door hotspot
    plus any flavor props come from store-specific callers.
    """
    s = Scene(key, name, w, h, tile, color, bg=bg, painted=True)
    s.add(Interactable("shop_door", "door",
                       round(door_tx * tile), round(door_ty * tile),
                       {"to": "town", "prompt": "Return to town"}))
    for p in props or []:
        s.add(Interactable(p["name"], "prop",
                           round(p["x"] * tile), round(p["y"] * tile),
                           {"text": p.get("text", "...")}))
    s.walk = walk
    s.spawn = (round(spawn[0] * tile), round(spawn[1] * tile))
    return s


def _weapon_store_props() -> list[dict]:
    return [
        {"name": "pegboard", "x": 19.0, "y": 7.0,
         "text": "Swords, axes and spears hang in neat rows. Pick a favorite."},
        {"name": "hide_wall", "x": 8.0, "y": 5.0,
         "text": "Beast hides from the rift hunters - good armor material."},
        {"name": "anvil_corner", "x": 33.5, "y": 9.5,
         "text": "Bram's smithing anvil. The steel rings true here."},
    ]


def _stone_store_props() -> list[dict]:
    return [
        {"name": "statue_alcoves", "x": 9.0, "y": 3.5,
         "text": "Guardian statues in waiting - they seem almost alive."},
        {"name": "kiln", "x": 34.5, "y": 5.0,
         "text": "The kiln roars. Heat rolls over your face."},
        {"name": "plans", "x": 8.0, "y": 10.6,
         "text": "Stoneworks sketches: a bridge, a vault, and rift-sealing runes."},
    ]


def _potion_store_props() -> list[dict]:
    return [
        {"name": "shelf_wall", "x": 8.0, "y": 6.0,
         "text": "Potions in every color line the shelves. Some are humming."},
        {"name": "ledger_book", "x": 12.8, "y": 12.2,
         "text": "An open ledger of recipes - half of it written in runes."},
        {"name": "ring_plants", "x": 25.0, "y": 5.5,
         "text": "Hanging herbs dry above the shelves."},
    ]


# Walk maps for the three painted stores (40x22, '.' = floor, '#' = solid).
# Weapon store: wall band + hanging gear rows 0-8, shelf table 0-13 / rack
# 4-13 on the left, counter L with the (sealed) keeper booth on the right,
# open floor behind the armor rack, door notch bottom-center.
_WEAPON_STORE_PATH = [
    "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40,
    "#"*14 + "."*12 + "#"*14,
    "#"*14 + "."*12 + "#"*14,
    "#"*14 + "."*12 + "#"*14,
    "#"*14 + "."*12 + "#"*14,
    "#"*5 + "."*21 + "#"*14,
    "#" + "."*8 + "#"*5 + "."*12 + "#"*14,   # rack cols 9-13, door front open
    "#" + "."*8 + "#"*5 + "."*12 + "#"*14,
    "#" + "."*8 + "#"*5 + "."*12 + "#"*14,
    "#" + "."*8 + "#"*5 + "."*12 + "#"*14,
    "#" + "."*37 + "##",
    "#" + "."*38 + "#",
    "#"*19 + "..." + "#"*18,
    "#"*19 + "..." + "#"*18,
]


def weapon_store_scene(w: int, h: int, tile: int) -> Scene:
    """Steelwright's Arms: the weapon shop (assets/backgrounds/wepon_store).
    Bram stands at the counter, reachable from the floor below it."""
    return store_scene(
        "shop_weapon", "Steelwright's Arms", "wepon_store", (120, 90, 70),
        _WEAPON_STORE_PATH, w, h, tile,
        door_tx=20.0, door_ty=20.6, spawn=(20.0, 19.2),
        props=_weapon_store_props())


# Stonemason store: statue alcoves + kiln band rows 0-6, stone stacks left,
# crates mid-top, workbench + log center-bottom, rubble edges, door notch
# bottom-center; the stonemason holds the open floor by the kiln.
_STONE_STORE_PATH = [
    "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40,
    "#####" + "."*6 + "#"*8 + "."*20 + "#",
    "#####" + "."*6 + "#"*8 + "."*20 + "#",
    "#####" + "."*34 + "#",
    "#####" + "."*34 + "#",
    "#####" + "."*34 + "#",
    "####" + "."*7 + "####" + "."*24 + "#",
    "####" + "."*7 + "####" + "."*24 + "#",
    "#"*10 + "."*9 + "#"*11 + "."*9 + "#",
    "#"*10 + "."*9 + "#"*11 + "."*9 + "#",
    "#"*10 + "."*9 + "#"*11 + "."*9 + "#",
    "#"*10 + "."*29 + "#",
    "#"*10 + "."*29 + "#",
    "#"*16 + "."*6 + "#"*18,
    "#"*16 + "."*6 + "#"*18,
    "#"*16 + "."*6 + "#"*18,
]


def stone_store_scene(w: int, h: int, tile: int) -> Scene:
    """Rubble's Stoneworks: the stonemason's hall (stonemaisen_store.png)."""
    return store_scene(
        "shop_stone", "Rubble's Stoneworks", "stonemaisen_store",
        (105, 105, 110), _STONE_STORE_PATH, w, h, tile,
        door_tx=18.5, door_ty=20.6, spawn=(18.5, 19.2),
        props=_stone_store_props())


# Potion store: shelf wall rows 0-11 (with a closed gap mid-top), the big
# shop table 8-21 rows 12-16, corner rack left, glowing bottles bottom-right,
# door notch bottom-center at cols 15-19.
_POTION_STORE_PATH = [
    "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40, "#"*40,
    "#"*20 + "."*6 + "#"*14,
    "#"*20 + "."*6 + "#"*14,
    "#"*20 + "."*6 + "#"*14,
    "#"*20 + "."*6 + "#"*14,
    "#"*20 + "."*6 + "#"*14,
    "..." + "###" + ".." + "#"*14 + "."*17 + "#",
    "..." + "###" + ".." + "#"*14 + "."*17 + "#",
    "..." + "###" + ".." + "#"*14 + "."*17 + "#",
    "........" + "#"*14 + "."*17 + "#",
    "........" + "#"*14 + "."*17 + "#",
    "#" + "."*29 + "#"*8 + "." + "#",
    "#" + "."*29 + "#"*8 + "." + "#",
    "#"*15 + "."*5 + "#"*20,
    "#"*15 + "."*5 + "#"*20,
    "#"*15 + "."*5 + "#"*20,
]


def potion_store_scene(w: int, h: int, tile: int) -> Scene:
    """Fennwick's Brews: the potion shop (potion_room.png)."""
    return store_scene(
        "shop_potion", "Fennwick's Brews", "potion_room", (90, 120, 100),
        _POTION_STORE_PATH, w, h, tile,
        door_tx=17.5, door_ty=20.6, spawn=(17.5, 19.2),
        props=_potion_store_props())


def beyond_scene(w: int, h: int, tile: int) -> Scene:
    """Rifts & Beyond: the path past the town sign (art pending: colored grid).

    A scarred field of fallen rift stones; prop stones are inspectable and
    a gate at the bottom leads back to town.
    """
    s = Scene("beyond", "Rifts & Beyond", w, h, tile, (70, 55, 95))
    s.add(Interactable("gate_back", "gate",
                       round((w // 2) * tile), round((h - 2) * tile),
                       {"to": "town", "label": "Town"}))
    for nm, tx, ty, txt in (
            ("fallen_menhirs", 8.5, 5.5,
             "Menhirs sheared clean in half. Whatever opened this rift left fast."),
            ("rift_scars", 20.0, 8.0,
             "Hairline scars of light crawl across the ground here."),
            ("watching_stone", 30.5, 12.5,
             "A carved eye watches the horizon. It blinks when you look away.")):
        s.add(Interactable(nm, "prop", round(tx * tile), round(ty * tile),
                           {"text": txt}))
    s.spawn = (round((w // 2) * tile), round((h - 3) * tile))
    return s


def gardens_scene(w: int, h: int, tile: int) -> Scene:
    """The Magical Gardens: bloom-lined paths (art pending: colored grid).

    A bench and a small pond are inspects; the gate at the bottom leads back
    to town.
    """
    s = Scene("gardens", "The Magical Gardens", w, h, tile, (70, 130, 80))
    s.add(Interactable("gate_back", "gate",
                       round((w // 2) * tile), round((h - 2) * tile),
                       {"to": "town", "label": "Town"}))
    for nm, tx, ty, txt in (
            ("pond", 17.5, 8.0,
             "Pond lilies glow faintly. The water reflects stars that aren't there."),
            ("moon_bench", 26.0, 12.0,
             "A bench of living wood, grown into a perfect seat."),
            ("singing_flowers", 10.5, 14.0,
             "These flowers hum the tune the town bell used to play.")):
        s.add(Interactable(nm, "prop", round(tx * tile), round(ty * tile),
                           {"text": txt}))
    s.spawn = (round((w // 2) * tile), round((h - 3) * tile))
    return s

