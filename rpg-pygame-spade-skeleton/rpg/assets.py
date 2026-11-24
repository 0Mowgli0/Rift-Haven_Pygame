"""AssetManager: central PNG loader with scaled rendering + labeled fallback.

Every sprite in the game goes through here so missing files never crash:
a missing PNG becomes a colored rectangle with the entity's short label.

Scaling (config.yaml `render:`): sprites are scaled proportionally to a
target height (player 72px, enemy 64px, boss 192px on 1280x720 — Stardew
proportions, ~2 tiles tall), keeping characters consistent with the tile
size. Collision boxes use hitbox_scale separately (see state.py), staying
smaller than the sprite.
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
        self._cache: dict[str, pygame.Surface] = {}
        self._backgrounds: dict[str, pygame.Surface | None] = {}
        self._font_cache: Font | None = None

    # ------------------------------------------------------------------ sprites
    def sprite(self, subfolder: str, filename: str, height: int,
               label: str = "?", color: tuple[int, int, int] | None = None
               ) -> pygame.Surface:
        """Return a sprite scaled proportionally to `height` px tall."""
        key = f"{subfolder}/{filename}@{height}"
        if key not in self._cache:
            path: Path = ASSETS / subfolder / filename
            if path.exists():
                surf = pygame.image.load(str(path)).convert_alpha()
                w = max(1, round(surf.get_width() * height / surf.get_height()))
                surf = pygame.transform.smoothscale(surf, (w, height))
            else:
                surf = self._fallback(label, (height, height), color)
            self._cache[key] = surf
        return self._cache[key]

    def get(self, subfolder: str, filename: str, label: str,
            color: tuple[int, int, int] | None = None) -> pygame.Surface:
        """Legacy tile-sized sprite (32x32); prefer sprite() for characters."""
        return self.sprite(subfolder, filename, self.tile, label, color)

    def _fallback(self, label: str, size: tuple[int, int],
                  color: tuple[int, int, int] | None) -> pygame.Surface:
        """Colored labeled rectangle: the game must never crash on missing art."""
        color = color or (200, 60, 60)
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=6)
        pygame.draw.rect(surf, (255, 255, 255), surf.get_rect(), 2, border_radius=6)
        name = self._font().render(label[:3], True, (255, 255, 255))
        surf.blit(name, name.get_rect(center=surf.get_rect().center))
        return surf

    # -------------------------------------------------------------- backgrounds
    def background(self, name: str, size: tuple[int, int]) -> pygame.Surface | None:
        """Return a screen-sized background from assets/backgrounds/, or None."""
        key = f"{name}@{size[0]}x{size[1]}"
        if key not in self._backgrounds:
            path: Path = ASSETS / "backgrounds" / f"{name}.png"
            surf: pygame.Surface | None = None
            if path.exists():
                surf = pygame.image.load(str(path)).convert()
                if surf.get_size() != size:
                    surf = pygame.transform.smoothscale(surf, size)
            self._backgrounds[key] = surf
        return self._backgrounds[key]

    # -------------------------------------------------------------------- misc
    def _font(self) -> Font:
        if self._font_cache is None:
            self._font_cache = pygame.font.SysFont("consolas,monospace", 14)
        return self._font_cache
