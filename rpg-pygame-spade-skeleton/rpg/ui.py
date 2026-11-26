"""All pygame drawing: world, HUD, menus, overlays. No game logic here."""

from __future__ import annotations

import math

import pygame

from .assets import AssetManager
from .state import GameState
from .world import nearest_interactable, portal_locked
from . import fsm as F

# Interactable kind -> (asset subfolder, file, render height px, E-prompt verb).
# Sprites are scaled proportionally; missing files draw labeled placeholders.
# prop/food have no sprite (text-only prompts); height 0 skips drawing.
KIND_SPRITES = {
    "bed": ("furniture", "bed.png", 48, "Sleep"),
    "door": ("furniture", "door.png", 64, "Enter"),
    "station": ("furniture", "upgrade_station.png", 96, "Upgrade"),
    "trophy": ("furniture", "trophy_cabinet.png", 48, "View"),
    "chest": ("items", "chest_closed.png", 48, "Open"),
    "portal": ("items", "portal.png", 96, "Travel"),  # fallback when art arrives
    "exit": ("items", "portal.png", 48, "Haven"),
    "gate": ("items", "prop.png", 0, "Travel"),  # signposts/doors, art-drawn
    "prop": ("items", "prop.png", 0, "Inspect"),
    "food": ("items", "prop.png", 0, "Eat"),
}

# On painted scenes (real full-screen artwork) these kinds come from the
# picture itself; drawing the placeholder sprite would double them.
PAINTED_KINDS = {"bed", "door", "chest", "trophy", "prop", "food"}

FURNITURE_PLACEHOLDER: dict[str, tuple[int, int, int]] = {
    "bed": (120, 90, 180),
    "door": (140, 100, 60),
    "station": (200, 160, 60),
    "trophy": (230, 200, 90),
}


def npc_rescuable(gs: GameState, npc: dict) -> bool:
    """True if this chained character can be freed (boss beaten, not yet)."""
    return (bool(npc.get("rescue_after_boss"))
            and npc["rescue_after_boss"] in gs.inv.collected_bosses
            and npc["id"] not in gs.rescued_npcs)


def draw_world(surf: pygame.Surface, gs: GameState, am: AssetManager) -> None:
    """Render scene, portals, mobs, boss, player, props, E-prompt."""
    gs.scene.draw(surf, am)
    tile = gs.s.tile
    t_ms = pygame.time.get_ticks()
    # Animated portals first: their glow sits behind everything else.
    # Painted hub scenes show the artwork's own portals; no moving overlay.
    # Locked rifts are signalled by the "[Locked]" prompt + E message instead.
    for it in gs.scene.interactables:
        if it.kind == "portal":
            if not gs.scene.painted:
                locked = portal_locked(gs, it)
                color = ((95, 95, 110) if locked
                         else tuple(it.data.get("portal_color",
                                                (150, 90, 240))))
                _draw_portal(surf, it.x + tile / 2, it.y + tile / 2, t_ms,
                             color, 96, locked)
        elif it.kind == "exit":
            _draw_portal(surf, it.x + tile / 2, it.y + tile / 2, t_ms,
                         (90, 150, 255), 48, locked=False)
    for m in gs.mobs:
        if m.alive:
            img = am.sprite("enemies", f"{m.kind}.png", gs.s.enemy_height,
                            m.kind[:3], m.color)
            cx, cy = m.x + tile / 2, m.y + tile / 2
            surf.blit(img, img.get_rect(center=(cx, cy)))
            if m.flash > 0:  # white hit-flash overlay
                flash = img.copy()
                flash.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_ADD)
                surf.blit(flash, flash.get_rect(center=(cx, cy)))
            _hp_bar(surf, m.x, m.y - 10, m.shown_hp / m.max_hp, 32)
    if gs.boss and gs.boss.alive:
        b = gs.boss
        img = am.sprite("bosses", f"{b.kind}.png", gs.s.boss_height,
                        b.kind[:3], b.color)
        surf.blit(img, img.get_rect(center=(b.x, b.y)))
        if b.flash > 0:
            flash = img.copy()
            flash.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(flash, flash.get_rect(center=(b.x, b.y)))
        w = surf.get_width() // 3
        _hp_bar(surf, (surf.get_width() - w) // 2, 30, b.shown_hp / b.max_hp, w)
    p = gs.player
    cid = gs.character_id or "knight"
    img = am.sprite("player", f"{cid}.png", gs.s.player_height, "P",
                    (70, 130, 220))
    # Player idle-life: breathing bob while standing still, a small step-hop
    # while moving, a soft ground shadow, and a sideways glance after a few
    # idle seconds (calm scenes only, Stardew/Undertale flavor).
    t_s = t_ms / 1000.0
    if gs.idle_t > 0.1:
        bob = math.sin(t_s * 2.2) * 1.6
    else:
        bob = abs(math.sin(t_s * 10.0)) * 2.5
    face = gs.player_face
    if gs.phase in (F.HOME, F.OUTSIDE, F.TOWN) and gs.idle_t > 3.0 \
            and (gs.idle_t - 3.0) % 7.0 < 1.2:
        face = -1
    if face < 0:
        img = pygame.transform.flip(img, True, False)
    shadow = pygame.Surface((max(14, round(img.get_width() * 0.55)), 7),
                            pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
    surf.blit(shadow, shadow.get_rect(
        midbottom=(p.x, p.y + gs.s.player_height / 2)))
    surf.blit(img, img.get_rect(center=(p.x, p.y - bob)))
    # Player HP bar above the sprite while combat is active (spec section 4).
    if gs.phase in (F.AREA_MOBS, F.BOSS_FIGHT):
        _hp_bar(surf, p.x - 24, p.y - gs.s.player_height * 0.62,
                p.stats.shown_hp / p.stats.max_hp, 48, 6, (60, 200, 255))
    # Projectiles (rotated sprite art or fallback glow) + slash arcs.
    for prj in gs.projectiles:
        _draw_projectile(surf, am, prj)
    # Floating damage numbers.
    f_num = pygame.font.SysFont("monospace", 15, bold=True)
    for t in gs.texts:
        surf.blit(f_num.render(t.text, True, t.color),
                  (t.x, t.y - 6))
    # Solid props stand on their interaction tile, sprite anchored bottom.
    # Painted scenes already show their furniture in the artwork (PAINTED_KINDS).
    for it in gs.scene.interactables:
        if it.kind in ("portal", "exit"):
            continue
        folder, fname, height, _ = KIND_SPRITES.get(
            it.kind, ("items", f"{it.kind}.png", 48, "Inspect"))
        if height <= 0:      # art-drawn kinds (prop/food/gate): no sprite
            continue
        if gs.scene.painted and it.kind in PAINTED_KINDS:
            continue
        img = am.sprite(folder, fname, height, it.name[0].upper(),
                        FURNITURE_PLACEHOLDER.get(it.kind, (220, 180, 60)))
        surf.blit(img, img.get_rect(midbottom=(it.x + tile / 2,
                                               it.y + tile + 4)))
    # NPCs (data-driven from data/npcs.json) at their placed tile positions,
    # drawn a touch taller than the player, Stardew-style. Lifelike layer:
    # breathing bob, soft ground shadow, facing flips (see tick_npcs).
    npc_h = round(gs.s.player_height * 1.6)
    for n in gs.npcs:
        if n.get("scene") != gs.area_id:
            continue
        rt = gs.npc_rt.get(n["id"], {})
        nx, ny = n["x"] * tile, n["y"] * tile
        img = am.sprite("npcs", n.get("sprite", ""), npc_h,
                        n["name"][0].upper(),
                        tuple(n.get("color", (200, 180, 120))))
        if rt.get("face", 1) < 0:
            img = pygame.transform.flip(img, True, False)
        bob = math.sin(t_s * 2.0 + rt.get("hop", 0.0)) * 1.5  # gentle breath
        shadow = pygame.Surface((max(12, round(img.get_width() * 0.6)), 7),
                                pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        surf.blit(shadow, shadow.get_rect(
            midbottom=(nx + tile / 2, ny + tile - 1)))
        surf.blit(img, img.get_rect(
            midbottom=(nx + tile / 2, ny + tile - 2 - bob)))
        # E: Talk prompt when the player is close (decked below near prompt).
        if ((p.x - nx) ** 2 + (p.y - ny) ** 2) ** 0.5 <= tile * 3.0:
            ftalk = pygame.font.SysFont("monospace", 15, bold=True)
            verb = "[E] Shop" if n.get("shop") else "[E] Talk"
            txt = ftalk.render(verb if not npc_rescuable(gs, n)
                               else "[E] Free them!", True, (140, 255, 160))
            surf.blit(txt, (nx + tile / 2 - txt.get_width() / 2, ny - 22))
    # "Press E" prompt near the interactable the player is standing at.
    near = nearest_interactable(gs.scene, p.x, p.y, tile * 2.0)
    if near is not None:
        _, _, _, verb = KIND_SPRITES.get(near.kind,
                                         ("items", "", 0, near.name.title()))
        verb = near.data.get("prompt", verb)
        f = pygame.font.SysFont("monospace", 15, bold=True)
        if near.kind == "portal" and portal_locked(gs, near):
            req = gs.data["areas"][near.data["area"]].get("requires", "?")
            boss_name = gs.data["bosses"].get(req, {}).get("name", req)
            txt = f.render(f"[Locked] Defeat {boss_name}", True, (170, 170, 180))
        else:
            txt = f.render(f"[E] {verb}", True, (255, 235, 120))
        px = near.x + tile / 2 - txt.get_width() / 2
        surf.blit(txt, (px, near.y - 22))


_GLOW_CACHE: dict[tuple, pygame.Surface] = {}


def _glow(color: tuple[int, int, int], radius: int) -> pygame.Surface:
    """Cached radial glow sprite (soft halo behind a portal)."""
    key = (color, radius)
    if key not in _GLOW_CACHE:
        size = radius * 2 + 2
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(6):
            f = 1.0 - i / 6
            r = int(radius * (0.4 + 0.6 * (i / 6)))
            a = int(70 * f)
            pygame.draw.circle(s, (*color, a), (size // 2, size // 2), r)
        _GLOW_CACHE[key] = s
    return _GLOW_CACHE[key]


def _draw_portal(surf: pygame.Surface, cx: float, cy: float, t_ms: int,
                 color: tuple[int, int, int], height: int,
                 locked: bool) -> None:
    """Animated swirling portal: glow, rotating spiral arms, orbit particles.

    Drawn procedurally (not a square); when portal art files land in
    assets/effects/ they can replace frame drawing, but this looks good
    without any asset. Locked portals are dim, slow, particle-free.
    """
    r = height / 2
    squash = 0.62                       # vertical squash -> portal ellipse
    if not locked:
        surf.blit(_glow(color, int(r * 1.5)),
                  _glow(color, int(r * 1.5)).get_rect(center=(cx, cy)))
    col = (140, 140, 155) if locked else color
    dark = (25, 22, 35) if locked else (15, 10, 25)
    speed = 0.0008 if locked else 0.0022
    # dark center hole
    pygame.draw.ellipse(surf, dark, pygame.Rect(cx - r * 0.75, cy - r * 0.75
                                                * squash, r * 1.5,
                                                r * 1.5 * squash))
    # three spiral arms
    for arm in range(3):
        pts = []
        for s_i in range(25):
            f = s_i / 24
            ang = t_ms * speed + arm * (2 * math.pi / 3) + f * 4.4
            rad = r * (1.05 - 0.95 * f)
            pts.append((cx + math.cos(ang) * rad,
                        cy + math.sin(ang) * rad * squash))
        pygame.draw.lines(surf, col, False, pts, 3)
    # rim ring (counter-rotating highlights)
    for k in range(8):
        ang = -t_ms * speed * 0.6 + k * (2 * math.pi / 8)
        px = cx + math.cos(ang) * r * 1.08
        py = cy + math.sin(ang) * r * 1.08 * squash
        pygame.draw.circle(surf, col, (int(px), int(py)), 2)
    # orbiting particles (skip when locked)
    if not locked:
        for i in range(10):
            seed = i * 2.399 + math.sin(i)  # golden-angle spread, stable
            ang = t_ms * speed * 1.6 + seed
            rad = r * (0.55 + 0.42 * abs(math.sin(seed)))
            px = cx + math.cos(ang) * rad
            py = cy + math.sin(ang) * rad * squash
            bright = tuple(min(255, c + 90) for c in color)
            pygame.draw.circle(surf, bright, (int(px), int(py)), 2)


def _hp_bar(surf, x: float, y: float, frac: float, width: int = 32,
            height: int = 4, color: tuple[int, int, int] = (0, 220, 0)) -> None:
    r = pygame.Rect(int(x), int(y), width, height)
    pygame.draw.rect(surf, (40, 0, 0), r)
    pygame.draw.rect(surf, color,
                     (r.x, r.y, int(width * max(0.0, min(1.0, frac))), height))


def _draw_projectile(surf: pygame.Surface, am: AssetManager, prj) -> None:
    """One projectile: rotated sprite art if it exists, glow circle if not."""
    if prj.kind == "slash":
        r = prj.radius
        a0 = math.radians(prj.angle - 65)
        rect = pygame.Rect(int(prj.x - r), int(prj.y - r), int(r * 2),
                           int(r * 2))
        pygame.draw.arc(surf, (255, 240, 150), rect, a0, a0 + math.pi / 1.5, 5)
        return
    name = prj.sprite or "plasma_ball.png"
    rotate = name.startswith(("arrow", "dagger"))
    img = am.sprite("projectiles", name,
                    12 if name.startswith("arrow") else 16,
                    name[0].upper(), (120, 200, 255))
    if rotate:
        img = pygame.transform.rotate(img, -prj.angle)
    surf.blit(img, img.get_rect(center=(prj.x, prj.y)))


def draw_hud(surf: pygame.Surface, gs: GameState) -> None:
    """Top bar: HP, gold, phase, area, weapon."""
    f = pygame.font.SysFont("monospace", 16)
    st = gs.player.stats
    ch = gs.data["characters"].get(gs.character_id, {})
    lines = [
        f"{ch.get('name', 'Hero')} ({ch.get('title', '-')})  "
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


# --------------------------------------------------------------------- menus
def draw_start_menu(surf: pygame.Surface, items: list[str], idx: int) -> None:
    """Title screen: New Game / Continue / Settings / Quit."""
    surf.fill((15, 15, 25))
    w, h = surf.get_size()
    title = pygame.font.SysFont("monospace", 48, bold=True).render(
        "RIFT HAVEN", True, (255, 215, 0))
    surf.blit(title, title.get_rect(center=(w // 2, h // 4)))
    f = pygame.font.SysFont("monospace", 24)
    y = int(h * 0.45)
    for i, it in enumerate(items):
        color = (255, 255, 80) if i == idx else (200, 200, 200)
        text = f"> {it}" if i == idx else it
        surf.blit(f.render(text, True, color), (w // 2 - 80, y))
        y += 34
    hint = pygame.font.SysFont("monospace", 14).render(
        "Up/Down: move   Enter: select   Esc: quit", True, (140, 140, 140))
    surf.blit(hint, (w // 2 - hint.get_width() // 2, h - 40))


def draw_character_select(surf: pygame.Surface, gs: GameState,
                          am: AssetManager, order: list[str], idx: int) -> None:
    """Character cards with preview, name, stats; locked ones dimmed."""
    surf.fill((15, 15, 25))
    w, h = surf.get_size()
    title = pygame.font.SysFont("monospace", 32, bold=True).render(
        "CHOOSE YOUR CHARACTER", True, (255, 215, 0))
    surf.blit(title, title.get_rect(center=(w // 2, 40)))
    card_w, card_h, gap = 230, 380, 24
    x0 = (w - 4 * card_w - 3 * gap) // 2
    y0 = int(h * 0.18)
    for i, cid in enumerate(order):
        c = gs.characters()[cid]
        locked = cid not in gs.unlocked_characters
        r = pygame.Rect(x0 + i * (card_w + gap), y0, card_w, card_h)
        pygame.draw.rect(surf, (40, 40, 60) if i == idx else (25, 25, 38), r,
                         border_radius=10)
        pygame.draw.rect(surf, (255, 215, 0) if i == idx else (90, 90, 110),
                         r, 2, border_radius=10)
        prev = am.sprite("player", c["sprite"], 96, c["title"][:3],
                         (120, 120, 140))
        prev = prev if not locked else prev.copy()
        if locked:
            prev.set_alpha(90)
        surf.blit(prev, prev.get_rect(center=(r.centerx, r.y + 80)))
        f = pygame.font.SysFont("monospace", 18, bold=True)
        surf.blit(f.render(c["name"], True, (255, 255, 255)),
                  (r.x + 14, r.y + 150))
        f2 = pygame.font.SysFont("monospace", 14)
        surf.blit(f2.render(c["title"] + (" (locked)" if locked else ""), True,
                            (170, 200, 255) if not locked else (150, 150, 150)),
                  (r.x + 14, r.y + 172))
        st = c["stats"]
        for j, ln in enumerate((f"HP {st['hp']}", f"ATK {st['attack']}",
                                f"DEF {st['defense']}", f"SPD {st['speed']}")):
            surf.blit(f2.render(ln, True, (220, 220, 220)),
                      (r.x + 14, r.y + 198 + 18 * j))
        surf.blit(f2.render(c["attack_style"], True, (180, 180, 120)),
                  (r.x + 14, r.y + card_h - 60))
        if locked:
            lf = pygame.font.SysFont("monospace", 15, bold=True)
            surf.blit(lf.render("LOCKED", True, (255, 90, 90)),
                      (r.centerx - 34, r.y + 118))
    hint = pygame.font.SysFont("monospace", 14).render(
        "Left/Right: choose   Enter: confirm   Esc: back", True, (140, 140, 140))
    surf.blit(hint, (w // 2 - hint.get_width() // 2, h - 40))


def draw_settings(surf: pygame.Surface, gs: GameState, idx: int) -> None:
    """Settings page: volume, fullscreen, difficulty (placeholder), back."""
    surf.fill((15, 15, 25))
    w, h = surf.get_size()
    title = pygame.font.SysFont("monospace", 32, bold=True).render(
        "SETTINGS", True, (255, 215, 0))
    surf.blit(title, title.get_rect(center=(w // 2, 60)))
    rows = [
        f"Volume    <{int(gs.s.volume * 10) * '#':<10}> {gs.s.volume:.0%}",
        f"Fullscreen  <{'On' if gs.s.fullscreen else 'Off'}>",
        f"Difficulty  <{gs.s.difficulty}>  (placeholder)",
        "Back",
    ]
    f = pygame.font.SysFont("monospace", 22)
    y = int(h * 0.3)
    for i, ln in enumerate(rows):
        color = (255, 255, 80) if i == idx else (200, 200, 200)
        text = f"> {ln}" if i == idx else ln
        surf.blit(f.render(text, True, color), (w // 2 - 160, y))
        y += 44
    hint = pygame.font.SysFont("monospace", 14).render(
        "Up/Down: move   Left/Right & Enter: adjust   Esc: back", True,
        (140, 140, 140))
    surf.blit(hint, (w // 2 - hint.get_width() // 2, h - 40))


def draw_overlays(surf: pygame.Surface, gs: GameState,
                  am: AssetManager | None = None) -> None:
    """Reward / game-over / end / pause / upgrade / inventory / dialogs."""
    if gs.phase == F.REWARD:
        _center_text(surf, "REWARD: boss collected! (ENTER: outside)", (255, 215, 0))
    elif gs.phase == F.GAME_OVER:
        _center_text(surf, "GAME OVER (ENTER: revive at base)", (255, 90, 90))
    elif gs.phase == F.END:
        _center_text(surf, "VICTORY! All bosses defeated. (ESC: return home)",
                     (120, 255, 120))
    elif gs.phase == F.PAUSED:
        _panel(surf, ["PAUSED",
                      "Enter/Esc: resume",
                      "S: save slot",
                      "H: save & quit to title",
                      "Q: quit without saving"])
    elif gs.phase == F.INVENTORY:
        _draw_inventory_ui(surf, gs, am or AssetManager(gs.s.tile))
    elif gs.phase == F.SHOP:
        _draw_shop_ui(surf, gs)
    elif gs.phase == F.UPGRADE:
        wep = gs.inv.equipped_weapon()
        _panel(surf, [
            f"UPGRADE STATION   (gold: {gs.inv.gold}g)",
            "1: HP +10          30g    2: Attack +1   30g",
            "3: Defense +1      30g    4: Speed +10   30g",
            f"5: {(wep.name if wep else '-')} +1 level",
            "Esc: close",
        ])
    elif gs.open_chest is not None:
        _draw_chest_ui(surf, gs, am or AssetManager(gs.s.tile))
    elif gs.open_dialogue is not None:
        _draw_dialogue_box(surf, gs)
    elif gs.trophy_menu:
        _panel(surf, _trophy_lines(gs))


def _slot_rect(surf: pygame.Surface, col: int, row: int, size: int = 48,
               pad: int = 6, left: int = 0, top: int = 0) -> pygame.Rect:
    return pygame.Rect(left + col * (size + pad), top + row * (size + pad),
                       size, size)


def _draw_grid(surf: pygame.Surface, stacks: list, sel: int, am: AssetManager,
               left: int, top: int, cols: int = 4,
               sprite_folder: str = "items") -> pygame.Rect | None:
    """One inventory grid: slots, stack icons, qty, selection. Returns sel rect."""
    sel_rect = None
    small = pygame.font.SysFont("monospace", 12, bold=True)
    for gr, st in enumerate(stacks):
        col, row = gr % cols, gr // cols
        r = _slot_rect(surf, col, row, left=left, top=top)
        pygame.draw.rect(surf, (35, 35, 50), r, border_radius=6)
        pygame.draw.rect(surf, (110, 110, 140), r, 1, border_radius=6)
        if st is not None and gr == sel:
            pygame.draw.rect(surf, (255, 215, 0), r, 2, border_radius=6)
            sel_rect = r
        if st is not None:
            spr = st.sprite or f"{st.item_id[0].upper()}.png"
            img = am.sprite(sprite_folder, spr, 32, st.name[0].upper(),
                            (140, 200, 140))
            surf.blit(img, img.get_rect(center=r.center))
            if st.qty > 1:
                surf.blit(small.render(str(st.qty), True, (255, 255, 160)),
                          (r.right - 16, r.bottom - 16))
    return sel_rect


def _category_rows(gs: GameState) -> list[str]:
    """Tooltips/headers for the inventory categories (spec section 5)."""
    inv = gs.inv
    return [
        f"Gold: {inv.gold}g",
        f"Weapons: {', '.join(w.name + ' L' + str(w.level) for w in inv.weapons.values()) or '-'}"
        f"   Equipped: {inv.equipped_weapon().name if inv.equipped_weapon() else '-'}",
        "Trophies: " + (", ".join(inv.collected_bosses) or "none"),
        "Materials/consumables in the grid   (arrow keys: move, Enter: use/move)",
    ]


def _tooltip(surf: pygame.Surface, gs: GameState, r: pygame.Rect,
             st) -> None:
    """Tooltip near a selected slot: name, kind, flavor text."""
    if st is None:
        return
    d = gs.data["items"].get(st.item_id, {})
    lines = [f"{st.name} x{st.qty}", d.get("kind", st.kind)]
    if d.get("desc"):
        lines.append(d["desc"])
    _panel(surf, lines)


def _draw_inventory_ui(surf: pygame.Surface, gs: GameState,
                       am: AssetManager) -> None:
    """Player inventory: grid of stack icons + categories + tooltip."""
    w, h = surf.get_size()
    _dim(surf)
    title = pygame.font.SysFont("monospace", 26, bold=True).render(
        "INVENTORY", True, (255, 215, 0))
    surf.blit(title, (w // 2 - 80, 40))
    f = pygame.font.SysFont("monospace", 15)
    y = 80
    for ln in _category_rows(gs):
        surf.blit(f.render(ln, True, (200, 200, 200)), (w // 2 - 220, y))
        y += 20
    r = _draw_grid(surf, gs.inv.items, gs.inv_slot, am, w // 2 - 220, y + 16)
    if r is not None and gs.inv_slot < len(gs.inv.items):
        _tooltip(surf, gs, r, gs.inv.items[gs.inv_slot])
    hint = pygame.font.SysFont("monospace", 14).render(
        "Arrows: select   E: use item   W: equip next weapon   I/Esc: close",
        True, (150, 150, 150))
    surf.blit(hint, (w // 2 - hint.get_width() // 2, h - 44))


def _draw_chest_ui(surf: pygame.Surface, gs: GameState,
                   am: AssetManager) -> None:
    """Two-pane chest UI: chest items left, player items right."""
    w, h = surf.get_size()
    _dim(surf)
    chest = gs.chests.get(gs.open_chest)
    f = pygame.font.SysFont("monospace", 22, bold=True)
    surf.blit(f.render("CHEST", True, (255, 215, 0)), (w // 4 - 40, 60))
    surf.blit(f.render("YOUR BAG", True, (255, 215, 0)), (3 * w // 4 - 70, 60))
    top = 100
    half = w // 2
    rc = _draw_grid(surf, (chest.items if chest else []), gs.chest_slot,
                    am, half - 220, top)
    ri = _draw_grid(surf, gs.inv.items, gs.inv_slot, am, 3 * w // 4 - 220,
                    top)
    f2 = pygame.font.SysFont("monospace", 14)
    surf.blit(f2.render("Tab: switch pane  E: move item  Esc: close",
                        True, (150, 150, 150)), (w // 2 - 160, h - 48))
    active = gs.chest_pane == "chest"
    if active and rc is not None and chest and gs.chest_slot < len(chest.items):
        _tooltip(surf, gs, rc, chest.items[gs.chest_slot])
    elif not active and ri is not None and gs.inv_slot < len(gs.inv.items):
        _tooltip(surf, gs, ri, gs.inv.items[gs.inv_slot])


def _draw_shop_ui(surf: pygame.Surface, gs: GameState) -> None:
    """Shop trade overlay: stock list left, your bag right, gold on top.

    Layout is list-style (Stardew flavor) instead of slot grids: each row is
    "name ... price" with the selected row highlighted; TAB switches panes,
    arrows move, E buys/sells, Esc leaves.
    """
    w, h = surf.get_size()
    _dim(surf)
    shop = gs.shop_def()
    f = pygame.font.SysFont("monospace", 24, bold=True)
    title = shop.get("title", "SHOP")
    surf.blit(f.render(title, True, (255, 215, 0)),
              (w // 4 - f.size(title)[0] // 2, 50))
    bt = "YOUR BAG (sell)"
    surf.blit(f.render(bt, True, (255, 215, 0)),
              (3 * w // 4 - f.size(bt)[0] // 2, 50))
    gold = f"Gold: {gs.inv.gold}g"
    fg = pygame.font.SysFont("monospace", 18, bold=True)
    surf.blit(fg.render(gold, True, (255, 220, 120)),
              (w - fg.size(gold)[0] - 20, 20))
    _shop_rows(surf, gs, pane_left=True)
    _shop_rows(surf, gs, pane_left=False)
    f2 = pygame.font.SysFont("monospace", 15)
    hint = ("Tab: switch pane   Up/Down: select   E: buy   Esc: leave"
            if gs.shop_pane == "stock"
            else "Tab: switch pane   Up/Down: select   E: sell   Esc: leave")
    # Description footer for the selected row.
    sel_row = (gs.shop_stock()[gs.shop_slot]
               if gs.shop_pane == "stock" and gs.shop_stock()
               and gs.shop_slot < len(gs.shop_stock()) else None)
    bag = gs.inv.items
    if gs.shop_pane == "bag" and bag and 0 <= gs.shop_slot < len(bag):
        d = gs.data["items"].get(bag[gs.shop_slot].item_id, {})
        val = d.get("value", 0)
        foot = (f"{bag[gs.shop_slot].name}  -  sells for "
                f"{max(1, round(val * 0.4))}g" if val and
                d.get("kind") != "trophy" else
                f"{bag[gs.shop_slot].name}")
    elif sel_row is not None:
        d = gs.data["items"].get(sel_row["id"], {}) \
            if sel_row["kind"] == "item" \
            else gs.data["weapons"].get(sel_row["id"], {})
        dmg = f"  damage {d['damage']}" if sel_row["kind"] == "weapon" \
            and "damage" in d else ""
        desc = d.get("desc", "")
        foot = f"{sel_row['name']}{dmg}  ({sel_row['kind']}: " \
               f"{'weapon' if sel_row['kind'] == 'weapon' else d.get('kind', 'item')})"
        if desc:
            foot += f"  -  {desc}"
    else:
        foot = "Nothing here."
    surf.blit(f2.render(foot, True, (200, 200, 200)), (40, h - 96))
    surf.blit(f2.render(hint, True, (150, 150, 150)),
              (w // 2 - f2.size(hint)[0] // 2, h - 48))


def _shop_rows(surf: pygame.Surface, gs: GameState, pane_left: bool
               ) -> list[tuple[int, int]]:
    """Draw one shop pane (rows of name/price); returns (top, bottom) per row."""
    f = pygame.font.SysFont("monospace", 16)
    x = w4 = (surf.get_width() // 4 - 180) if pane_left \
        else (3 * surf.get_width() // 4 - 180)
    y0 = 100
    active = (gs.shop_pane == "stock") == pane_left
    if pane_left:
        rows = gs.shop_stock()
        lines = [(f"{r['name']}  -  {r['price']}g", r) for r in rows]
    else:
        items = gs.inv.items
        lines = []
        for st in items:
            d = gs.data["items"].get(st.item_id, {})
            val = d.get("value", 0)
            sell = max(1, round(val * 0.4)) if val and d.get("kind") != "trophy" \
                else None
            qty = f" x{st.qty}" if st.qty > 1 else ""
            lines.append((f"{st.name}{qty}" + (f"  -  {sell}g" if sell
                                               else "  (not sellable)"), st))
    out = []
    if not lines:
        txt = f.render("(empty)", True, (120, 120, 130))
        surf.blit(txt, (x, y0))
        return []
    sel = gs.shop_slot if active else -1
    for i, (text, _) in enumerate(lines):
        y = y0 + i * 24
        if y > surf.get_height() - 140:
            break
        if active and i == sel:
            pygame.draw.rect(surf, (60, 50, 20), (x - 8, y - 3,
                                                  surf.get_width() // 2 - 40,
                                                  24), border_radius=4)
            pygame.draw.rect(surf, (255, 215, 0), (x - 8, y - 3,
                                                   surf.get_width() // 2 - 40,
                                                   24), 1, border_radius=4)
        img = f.render(text, True, (235, 235, 225))
        surf.blit(img, (x, y))
        out.append((x - 8, y - 3))
    return out


def _draw_dialogue_box(surf: pygame.Surface, gs: GameState) -> None:
    """NPC dialogue box at the screen bottom: speaker, text, continue hint."""
    d = gs.open_dialogue
    if not d:
        return
    w, h = surf.get_size()
    box = pygame.Rect(140, h - 190, w - 280, 150)
    pygame.draw.rect(surf, (18, 18, 28), box, border_radius=10)
    pygame.draw.rect(surf, (200, 180, 80), box, 2, border_radius=10)
    f = pygame.font.SysFont("monospace", 16, bold=True)
    surf.blit(f.render(d.get("speaker", "?"), True, (255, 215, 0)),
              (box.x + 20, box.y + 14))
    # wrap the text at ~80 chars
    f2 = pygame.font.SysFont("monospace", 15)
    words, lines, cur = d.get("text", "").split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 > 76:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    lines.append(cur)
    y = box.y + 44
    for ln in lines[:4]:
        surf.blit(f2.render(ln, True, (235, 235, 225)), (box.x + 20, y))
        y += 22
    hint = f2.render("E / Enter: continue", True, (150, 150, 150))
    surf.blit(hint, (box.right - hint.get_width() - 16, box.bottom - 26))


def draw_save_slots(surf: pygame.Surface, gs: GameState) -> None:
    """Slot picker used for both saving (pause) and loading (start menu)."""
    from .save import list_saves

    w, h = surf.get_size()
    _dim(surf)
    mode = "SAVE GAME" if gs.save_mode == "save" else "LOAD GAME"
    title = pygame.font.SysFont("monospace", 30, bold=True).render(
        mode, True, (255, 215, 0))
    surf.blit(title, title.get_rect(center=(w // 2, 90)))
    f = pygame.font.SysFont("monospace", 18)
    y = 150
    for i, meta in enumerate(list_saves(), start=1):
        if meta:
            line = (f"[{i}]  {meta['character'] or '?':<8}  "
                    f"bosses: {meta['bosses']}  {meta['time']}")
            color = (220, 220, 220)
        else:
            line = f"[{i}]  -- empty --"
            color = (120, 120, 130)
        if gs.save_mode == "load" and meta is None:
            color = (90, 90, 100)
        surf.blit(f.render(line, True, color), (w // 2 - 200, y))
        y += 40
    f2 = pygame.font.SysFont("monospace", 14)
    hint = ("1-3: save slot" if gs.save_mode == "save"
            else "1-3: load slot") + "   Esc: back"
    surf.blit(f2.render(hint, True, (150, 150, 150)),
              (w // 2 - f2.size(hint)[0] // 2, h - 50))


def _dim(surf: pygame.Surface) -> None:
    """Dark translucent scrim behind overlay panels."""
    s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, 160))
    surf.blit(s, (0, 0))


def _trophy_lines(gs: GameState) -> list[str]:
    """Trophy cabinet contents: bosses (empty slots too) + unlocked weapons."""
    lines = ["TROPHY CABINET", ""]
    for bid, b in gs.data["bosses"].items():
        mark = "[x]" if bid in gs.inv.collected_bosses else "[ ]"
        lines.append(f"{mark} {b['name']}")
    lines.append("")
    weps = [f"{w.name} (Lv {w.level})" for w in gs.inv.weapons.values()]
    lines.append("Weapons: " + (", ".join(weps) if weps else "none"))
    lines.append("E / Esc: close")
    return lines


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
