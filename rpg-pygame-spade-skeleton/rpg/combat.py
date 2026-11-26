"""Real-time combat core: projectiles, hit resolution, damage numbers, shake.

This module runs strictly inside the pygame loop (spec rule: XMPP is far too
slow for per-frame logic). The agent side still owns the orchestration: mob
spawn, boss phases, loot and death handling come back as protocol events
(mob_hit / mob_died / boss_hit / boss_died) that main.py forwards like any
other intent.

Hits are circle-vs-circle with hitbox_scale (boxes smaller than sprites per
spec). Knockback, hit flash and floating damage numbers are applied here;
only the agent-relevant *events* leave the module.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from . import fsm as F


@dataclass
class Projectile:
    """One flying attack: speed, range, damage, lifetime, collision."""
    x: float
    y: float
    vx: float
    vy: float
    damage: int
    range_max: float
    kind: str = "ranged"          # ranged | slash
    sprite: str | None = None     # file in assets/projectiles/, fallback orb
    traveled: float = 0.0
    radius: float = 7.0
    friendly: bool = True         # False = enemy fireball/ranged projectile

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def angle(self) -> float:
        return math.degrees(math.atan2(self.vy, self.vx))


@dataclass
class FloatingText:
    """Rising damage number (pure view state, lives 0.8 s)."""
    x: float
    y: float
    text: str
    color: tuple[int, int, int] = (255, 230, 90)
    life: float = 0.8


def try_fire(gs, tx: float, ty: float) -> list[dict]:
    """Fire the basic attack toward world point (tx, ty).

    Cooldown, range and projectile speed/sprite come from the selected
    character's data block (data/characters.json); the equipped weapon adds
    damage. Melee characters (projectile: null) get a short-lived wide arc
    slash instead. Ability slots 1-4 hook in here later (TODO).
    """
    if gs.attack_cd > 0:
        return []
    cid = gs.character_id or "knight"
    ch = gs.data["characters"][cid]
    gs.attack_cd = ch.get("attack_cooldown", 0.5)
    p = gs.player
    wep = gs.inv.equipped_weapon()
    dmg = ((wep.total_damage(p.stats.attack) if wep else p.stats.attack)
           + random.randint(0, 3))
    dx, dy = tx - p.x, ty - p.y
    d = math.hypot(dx, dy) or 1.0
    prj = ch.get("projectile")
    if prj:
        speed = prj.get("speed", 500)
        gs.projectiles.append(Projectile(
            x=p.x, y=p.y,
            vx=dx / d * speed, vy=dy / d * speed,
            damage=dmg, range_max=ch.get("attack_range", 400),
            kind="ranged", sprite=prj.get("sprite")))
    else:
        r = ch.get("attack_range", 56)
        speed = 720.0
        gs.projectiles.append(Projectile(
            x=p.x + dx / d * r * 0.5, y=p.y + dy / d * r * 0.5,
            vx=dx / d * speed, vy=dy / d * speed,
            damage=dmg, range_max=r * 0.6, kind="slash", radius=r / 2))
    return []


def tick(gs, dt: float) -> list[dict]:
    """One frame: cooldowns, smooth HP bars, projectiles, texts, shake."""
    events: list[dict] = []
    # -- smooth HP bar targets (lerp toward real hp) -------------------------
    _lerp_hp(gs.player.stats, dt)
    for m in gs.mobs:
        _lerp_entity(m, dt)
    if gs.boss:
        _lerp_entity(gs.boss, dt)
    # -- attack cooldown ------------------------------------------------------
    gs.attack_cd = max(0.0, gs.attack_cd - dt)
    # -- screen shake decay ----------------------------------------------------
    if gs.shake > 0:
        gs.shake = max(0.0, gs.shake - dt)
        mag = 7.0 * gs.shake
        gs.shake_offset = (random.uniform(-1, 1) * mag,
                           random.uniform(-1, 1) * mag)
    else:
        gs.shake_offset = (0, 0)
    # -- player hit flash decay -----------------------------------------------
    if gs.player.flash > 0:
        gs.player.flash = max(0.0, gs.player.flash - dt)
    # -- projectiles -----------------------------------------------------------
    for prj in list(gs.projectiles):
        prj.x += prj.vx * dt
        prj.y += prj.vy * dt
        prj.traveled += prj.speed * dt
        if prj.traveled >= prj.range_max:
            gs.projectiles.remove(prj)
            continue
        hit, evs = _collide(gs, prj)
        if hit:
            events += evs
            gs.projectiles.remove(prj)
    # -- floating damage numbers -------------------------------------------------
    for t in list(gs.texts):
        t.y -= 42 * dt
        t.life -= dt
        if t.life <= 0:
            gs.texts.remove(t)
    return events


def _lerp_hp(st, dt: float) -> None:
    """Player HP bar animates smoothly toward actual hp."""
    if st.shown_hp < 0:
        st.shown_hp = float(st.hp)
    diff = st.hp - st.shown_hp
    step = max(30.0, abs(diff) * 6.0) * dt
    st.shown_hp += max(-step, min(step, diff))


def _lerp_entity(e, dt: float) -> None:
    """Enemy/boss HP bar lerp + hit flash decay."""
    if e.shown_hp < 0:
        e.shown_hp = float(e.hp)
    diff = e.hp - e.shown_hp
    step = max(30.0, abs(diff) * 6.0) * dt
    e.shown_hp += max(-step, min(step, diff))
    if e.flash > 0:
        e.flash = max(0.0, e.flash - dt)


def _collide(gs, prj) -> tuple[bool, list[dict]]:
    """Circle test; friendly shots hit mobs/boss, enemy shots hit the player."""
    if not prj.friendly:
        p = gs.player
        rad = gs.s.player_height * gs.s.hitbox_scale / 2
        if math.hypot(p.x - prj.x, p.y - prj.y) < rad + prj.radius:
            player_hit(gs, prj.damage, prj.x - prj.vx, prj.y - prj.vy)
            return True, []
        return False, []
    for m in gs.mobs:
        if not m.alive:
            continue
        rad = gs.s.enemy_height * gs.s.hitbox_scale / 2
        if math.hypot(m.x - prj.x, m.y - prj.y) < rad + prj.radius:
            return True, [_damage(gs, m, prj.damage, prj.x - prj.vx,
                                  prj.y - prj.vy, "mob_hit", "mob_died")]
    b = gs.boss
    if b and b.alive:
        rad = gs.s.boss_height * gs.s.hitbox_scale / 2
        if math.hypot(b.x - prj.x, b.y - prj.y) < rad + prj.radius:
            gs.shake = max(gs.shake, 0.12)
            return True, [_damage(gs, b, prj.damage, prj.x - prj.vx,
                                  prj.y - prj.vy, "boss_hit", "boss_died",
                                  big=True)]
    return False, []


def player_hit(gs, damage: int, sx: float, sy: float, label: str = "") -> None:
    """One hit lands on the player (enemy contact or projectile)."""
    if gs.phase == F.GAME_OVER:
        return
    dmg = max(1, damage - gs.player.stats.defense)
    gs.player.stats.hp = max(0, gs.player.stats.hp - dmg)
    gs.player.flash = 0.14
    dx, dy = gs.player.x - sx, gs.player.y - sy
    d = math.hypot(dx, dy) or 1.0
    gs.scene.move(gs.player, dx / d * 26, dy / d * 26,
                  radius=gs.s.tile * 0.2)
    gs.texts.append(FloatingText(gs.player.x, gs.player.y - 44, str(dmg),
                                 (255, 90, 90)))
    gs.shake = max(gs.shake, 0.15)
    gs.log(f"{label} hits you for {dmg}!" if label else f"Hit for {dmg}!")
    if gs.player.stats.hp <= 0:
        gs.phase = F.GAME_OVER
        gs.log("You died... returning to base.")


def _damage(gs, e, dmg: int, sx: float, sy: float, hit_t: str,
            died_t: str, big: bool = False) -> dict:
    """Apply one hit: HP, defense, flash, knockback, number, shake.

    Returns the bridge event ('mob_hit'/'mob_died'/'boss_hit'/'boss_died').
    """
    dmg = max(1, dmg - e.defense)
    e.hp = max(0, e.hp - dmg)
    e.flash = 0.14
    dx, dy = e.x - sx, e.y - sy
    d = math.hypot(dx, dy) or 1.0
    kb = 34 if e is not gs.boss else 10
    gs.scene.move(e, dx / d * kb, dy / d * kb)
    gs.texts.append(FloatingText(e.x, e.y - 20, str(dmg)))
    if big or dmg >= 12:
        gs.shake = max(gs.shake, 0.22)
    ev = {"type": died_t if e.hp == 0 else hit_t,
          "id": e.id, "damage": dmg, "area": gs.area_id}
    if e is gs.boss:
        ev["hp"] = e.hp          # so the agent side can mirror boss phases
        ev["max_hp"] = e.max_hp
    return ev
