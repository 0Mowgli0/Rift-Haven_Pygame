"""All pygame drawing: HUD, menus, overlays. No game logic here."""

from __future__ import annotations

import pygame

from .assets import AssetManager
from .state import BOSS_FIGHT, END, GAME_OVER, MENU, REWARD, GameState


def draw_world(surf: pygame.Surface, gs: GameState, am: AssetManager) -> None:
    """Render scene, mobs, boss, player, interactables."""
    gs.scene.draw(surf, am)
    floor_img = am.get("tiles", "floor.png", "fl", (90, 70, 50))
    for m in gs.mobs:
        if m.alive:
            img = am.get("enemies", f"{m.kind}.png", m.kind[:3], m.color)
            surf.blit(img, (m.x, m.y))
            _hp_bar(surf, m.x, m.y - 8, m.hp / m.max_hp)
    if gs.boss and gs.boss.alive:
        b = gs.boss
        surf.blit(am.get("bosses", f"{b.kind}.png", b.kind[:3], b.color),
                  (b.x - 16, b.y - 16))
        _hp_bar(surf, b.x - 16, b.y - 24, b.hp / b.max_hp)
    p = gs.player
    surf.blit(am.get("player", "player.png", "P", (70, 130, 220)),
              (p.x - 12, p.y - 12))
    for it in gs.scene.interactables:
        img = am.get("items", f"{it.kind}.png", it.kind[0], (220, 180, 60))
        surf.blit(img, (it.x, it.y))


def _hp_bar(surf: pygame.Surface, x: float, y: float, frac: float) -> None:
    r = pygame.Rect(int(x), int(y), 32, 4)
    pygame.draw.rect(surf, (40, 0, 0), r)
    pygame.draw.rect(surf, (0, 220, 0), (r.x, r.y, int(32 * max(0, frac)), 4))


def draw_hud(surf: pygame.Surface, gs: GameState) -> None:
    """Top bar: HP, gold, phase, area, weapon."""
    f = pygame.font.SysFont("monospace", 16)
    st = gs.player.stats
    lines = [
        f"HP {st.hp}/{st.max_hp}  ATK {st.attack}  DEF {st.defense}",
        f"Gold {gs.inv.gold}g  Weapon {(gs.inv.equipped_weapon().name if gs.inv.equipped_weapon() else 'none')}"
        f" Lv{(gs.inv.equipped_weapon().level if gs.inv.equipped_weapon() else '-')}",
        f"Area {gs.area_id}  Phase {gs.phase}  Bosses {len(gs.inv.collected_bosses)}"
        f"/{len(gs.data['bosses'])}",
    ]
    y = 6
    for ln in lines:
        surf.blit(f.render(ln, True, (255, 255, 255)), (8, y))
        y += 18
    # message log (last 5)
    f2 = pygame.font.SysFont("monospace", 13)
    y = surf.get_height() - 90
    for msg in gs.messages[-5:]:
        surf.blit(f2.render(msg, True, (240, 240, 200)), (8, y))
        y += 16


def draw_overlays(surf: pygame.Surface, gs: GameState) -> None:
    """Menu / reward / game-over / end / upgrade screens."""
    w, h = surf.get_size()
    if gs.phase == MENU:
        _center_text(surf, "2D RPG SKELETON (spade + pygame)", (255, 255, 0))
        surf.blit(pygame.font.SysFont("monospace", 20).render(
            "Press ENTER to start, U for upgrades", True, (255, 255, 255)),
            (w // 2 - 220, h // 2))
    elif gs.phase == REWARD:
        _center_text(surf, "REWARD: boss collected! (ENTER: home)", (255, 215, 0))
    elif gs.phase == GAME_OVER:
        _center_text(surf, "GAME OVER (ENTER: revive at base)", (255, 90, 90))
    elif gs.phase == END:
        _center_text(surf, "VICTORY! All bosses defeated. (ESC: quit)", (120, 255, 120))
    elif gs.upgrade_menu:
        _panel(surf, [
            "UPGRADE SHOP (gold in HUD)",
            "1: HP +10HP/def  30g   2: Attack  30g",
            "3: Defense  30g         4: Speed   30g",
            "5: Weapon +1 level      6: Trophy list",
            "ESC: close",
        ])


def _center_text(surf: pygame.Surface, text: str, color) -> None:
    f = pygame.font.SysFont("monospace", 28, bold=True)
    r = f.render(text, True, color)
    surf.blit(r, r.get_rect(center=(surf.get_width() // 2,
                                    surf.get_height() // 3)))


def _panel(surf: pygame.Surface, lines: list[str]) -> None:
    box = pygame.Rect(0, 0, surf.get_width(), 30 + 20 * len(lines))
    box.center = surf.get_rect().center
    pygame.draw.rect(surf, (20, 20, 30), box)
    pygame.draw.rect(surf, (200, 180, 80), box, 2)
    f = pygame.font.SysFont("monospace", 16)
    y = box.y + 14
    for ln in lines:
        surf.blit(f.render(ln, True, (240, 240, 240)), (box.x + 20, y))
        y += 20
