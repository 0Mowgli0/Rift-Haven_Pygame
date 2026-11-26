"""AssetManager: central PNG loader with scaled rendering + labeled fallback.

Every sprite in the game goes through here so missing files never crash:
a missing PNG becomes a colored rectangle with the entity's short label.

Scaling (config.yaml `render:`): player/NPC frames are fitted to one tile
wide and the configured height; other sprites keep their source proportions.
Collision boxes use hitbox_scale separately, staying smaller than the sprite.
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
        self._actor_cache: dict[str, pygame.Surface] = {}
        self._backgrounds: dict[str, pygame.Surface | None] = {}
        self._font_cache: Font | None = None

    # ------------------------------------------------------------------ sprites
    def actor_sprite(self, subfolder: str, filename: str, height: int,
                     facing: str, label: str = "?",
                     color: tuple[int, int, int] | None = None
                     ) -> pygame.Surface:
        """Return a tile-width actor frame, using directional art when present."""
        stem = Path(filename).stem
        base_name = f"{stem}.png"
        direction_name = f"{stem}_{facing}.png"
        direction_path = ASSETS / subfolder / direction_name
        mirror = False

        if direction_path.exists():
            chosen = direction_name
        elif facing in ("left", "right"):
            opposite = "right" if facing == "left" else "left"
            opposite_name = f"{stem}_{opposite}.png"
            if (ASSETS / subfolder / opposite_name).exists():
                chosen = opposite_name
                mirror = True
            else:
                chosen = base_name
                mirror = facing == "left"
        else:
            chosen = base_name

        key = f"{subfolder}/{chosen}@{self.tile}x{height}:{facing}:{mirror}"
        if key not in self._actor_cache:
            img = self.sprite(subfolder, chosen, height, label, color)
            if mirror:
                img = pygame.transform.flip(img, True, False)
            target_size = (self.tile, height)
            if img.get_size() != target_size:
                img = pygame.transform.scale(img, target_size)
            self._actor_cache[key] = img
        return self._actor_cache[key]

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
