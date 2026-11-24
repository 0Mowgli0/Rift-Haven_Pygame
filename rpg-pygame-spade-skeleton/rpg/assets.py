"""AssetManager: PNGs from assets/, colored-rectangle fallback per category.

Fallback keeps the skeleton runnable before real art exists: a missing
file becomes a colored rect with the entity's short label drawn on it.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from .settings import ASSETS

Font = pygame.font.Font


class AssetManager:
    """Loads and caches sprites from assets/<subfolder>/<filename>."""

    def __init__(self, tile: int = 32) -> None:
        self.tile = tile
        self._cache: dict[str, pygame.Surface | None] = {}
        self._font_cache: Font | None = None

    def _font(self) -> Font:
        if self._font_cache is None:
            self._font_cache = pygame.font.SysFont("consolas,monospace", 14)
        return self._font_cache

    def background(self, name: str, size: tuple[int, int]) -> pygame.Surface | None:
        """Return a screen-sized background from assets/tiles/<name>.png, or None."""
        key = f"bg/{name}"
        if key not in self._cache:
            path: Path = ASSETS / "tiles" / f"{name}.png"
            surf: pygame.Surface | None = None
            if path.exists():
                surf = pygame.image.load(str(path)).convert()
                if surf.get_size() != size:
                    surf = pygame.transform.smoothscale(surf, size)
            self._cache[key] = surf
        return self._cache[key]

    def get(self, subfolder: str, filename: str, label: str,
            color: tuple[int, int, int] | None = None) -> pygame.Surface:
        """Return a scaled sprite; colored labeled rectangle if file missing."""
        key = f"{subfolder}/{filename}"
        if key in self._cache:
            return self._cache[key]
        path: Path = ASSETS / subfolder / filename
        if path.exists():
            surf = pygame.image.load(str(path)).convert_alpha()
            surf = pygame.transform.smoothscale(surf, (self.tile, self.tile))
        else:
            surf = self._fallback(label, color)
        self._cache[key] = surf
        return surf

    def _fallback(self, label: str,
                  color: tuple[int, int, int] | None) -> pygame.Surface:
        color = color or (200, 60, 60)
        surf = pygame.Surface((self.tile, self.tile), pygame.SRCALPHA)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=6)
        pygame.draw.rect(surf, (255, 255, 255), surf.get_rect(), 2, border_radius=6)
        name = self._font().render(label[:3], True, (255, 255, 255))
        surf.blit(name, name.get_rect(center=surf.get_rect().center))
        return surf
