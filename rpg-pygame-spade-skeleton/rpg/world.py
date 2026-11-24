"""Placeholder scene / tilemap.

A very small data-driven map: each Scene is a grid of walkable floor with a
wall border, plus named interaction points (portal, chest, stations).
Replace with Tiled/CSV loading later; the API (solid(), draw()) stays.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import pygame


@dataclass
class Interactable:
    """An interaction point in a scene (chest, portal, station...)."""
    name: str
    kind: str  # "portal" | "chest" | "station" | "trophy" | "exit"
    x: int
    y: int
    data: dict = field(default_factory=dict)


class Scene:
    """A rectangular tile grid with walls and interactables."""

    def __init__(self, key: str, name: str, w: int, h: int, tile: int,
                 color: tuple[int, int, int],
                 bg: str | None = None) -> None:
        self.key, self.name, self.tile = key, name, tile
        self.w, self.h = w, h
        self.color = color
        self.bg = bg  # background image name in assets/tiles/ (optional)
        # 1 = wall, 0 = floor. TODO: load real tilemaps.
        self.grid: list[list[int]] = [[0] * w for _ in range(h)]
        for x in range(w):
            self.grid[0][x] = self.grid[h - 1][x] = 1
        for y in range(h):
            self.grid[y][0] = self.grid[y][w - 1] = 1
        self.interactables: list[Interactable] = []

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
        # Background image if the scene has one, otherwise the color grid.
        img = assets.background(self.bg, surface.get_size()) if self.bg else None
        if img is not None:
            surface.blit(img, (0, 0))
            return
        for ty in range(self.h):
            for tx in range(self.w):
                r = pygame.Rect(tx * self.tile, ty * self.tile, self.tile, self.tile)
                if self.grid[ty][tx] == 1:
                    pygame.draw.rect(surface, (40, 40, 50), r)
                else:
                    base = tuple(min(255, c + ((tx + ty) % 2) * 8) for c in self.color)
                    pygame.draw.rect(surface, base, r)
        for it in self.interactables:
            r = pygame.Rect(it.x, it.y, self.tile, self.tile)
            pygame.draw.rect(surface, (230, 200, 60), r, border_radius=4)
            label = pygame.font.SysFont("monospace", 10).render(
                it.name[0].upper(), True, (0, 0, 0))
            surface.blit(label, label.get_rect(center=r.center))


def home_scene(w: int, h: int, tile: int) -> Scene:
    """Build the hub with all interaction stations + exit portal."""
    s = Scene("home", "Home Base", w, h, tile, (70, 90, 120), bg="home_base")
    s.add(Interactable("chest", "chest", 3 * tile, 3 * tile))
    s.add(Interactable("inventory", "chest", 5 * tile, 3 * tile))
    s.add(Interactable("weapon_smith", "station", 7 * tile, 3 * tile))
    s.add(Interactable("stat_station", "station", 9 * tile, 3 * tile))
    s.add(Interactable("trophy_room", "trophy", 11 * tile, 3 * tile))
    s.add(Interactable("portal_green_cave", "portal", (w // 2) * tile, (h // 2) * tile,
                       {"area": "green_cave"}))
    return s


def area_scene(key: str, name: str, w: int, h: int, tile: int,
                color: tuple[int, int, int]) -> Scene:
    """An explorable area; the exit back home is at the entrance."""
    s = Scene(key, name, w, h, tile, color,
              bg="boss_arena_magma" if key == "green_cave" else None)
    s.add(Interactable("exit_home", "exit", 2 * tile, 2 * tile, {"area": "home"}))
    return s
