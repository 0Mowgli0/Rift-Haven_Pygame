"""Per-frame enemy behaviour for the pygame loop (spec section 4 latency rule).

Four data-driven behaviors (data/enemies.json: "behavior"):
- charger  (fire slime): slow chase, winds up, then sprints at the player
- swoop    (cave bat):  orbits the player and dives in lunges
- caster   (lava imp):  keeps its distance and hurls fireballs
- melee    (skeleton):  walks up and swings on contact

Boss decisions (which attack, when) belong to the agent side / offline
director; this module only executes what was decided: telegraph windups,
phase-change reactions, fireball rings and slam radii. Everything here is per
frame, so it lives inside the pygame loop, never on XMPP.
"""

from __future__ import annotations

import math

from .combat import Projectile, player_hit

CONTACT_RANGE = 36


def tick_mobs(gs, dt: float) -> list[dict]:
    """Move every living mob per its behavior; returns combat events."""
    events: list[dict] = []
    for m in gs.mobs:
        if not m.alive:
            continue
        m.atk_cd = max(0.0, m.atk_cd - dt)
        events += BEHAVIORS.get(m.behavior, _melee)(gs, m, dt)
    return events


def tick_boss(gs, dt: float) -> list[dict]:
    """Boss per-frame: approach, phase transitions, telegraph resolution."""
    b = gs.boss
    if not (b and b.alive):
        return []
    events: list[dict] = []
    # phase changes at hp thresholds (66% / 33% ...) with a spoken line
    frac = b.hp / b.max_hp
    while b.phase_idx < len(b.phases) and frac <= b.phases[b.phase_idx]["at"]:
        line = b.phases[b.phase_idx].get("line", "...")
        gs.log(f"{b.name}: \"{line}\"")
        gs.shake = max(gs.shake, 0.30)
        b.phase_idx += 1
    # approach the player between attacks
    if b.tel <= 0:
        _approach(gs, b, b.speed * dt)
    # resolve a telegraphed attack once its windup elapses
    if b.tel > 0:
        b.tel -= dt
        if b.tel <= 0:
            events += _boss_strike(gs, b)
    return events


# ------------------------------------------------------------- behaviors
def _dir_to(gs, e) -> tuple[float, float]:
    dx, dy = gs.player.x - e.x, gs.player.y - e.y
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


def _dist(gs, e) -> float:
    return math.hypot(gs.player.x - e.x, gs.player.y - e.y)


def _approach(gs, e, dist_px: float) -> None:
    dx, dy = _dir_to(gs, e)
    gs.scene.move(e, dx * dist_px, dy * dist_px)


def _center(gs, e) -> tuple[float, float]:
    return e.x + gs.s.tile / 2, e.y + gs.s.tile / 2


def _contact_or_cast(gs, e, contact_cd: float) -> list[dict]:
    if _dist(gs, e) < CONTACT_RANGE and e.atk_cd <= 0:
        e.atk_cd = contact_cd
        return _hit_player(gs, e)
    return []


def _melee(gs, m, dt: float) -> list[dict]:
    """Skeleton grunt: steady walk, swing on contact."""
    _approach(gs, m, m.speed * dt)
    return _contact_or_cast(gs, m, 1.1)


def _charger(gs, m, dt: float) -> list[dict]:
    """Fire slime: slow chase, short blink telegraph, fast charge."""
    if m.tel > 0:  # winding up: stand still and blink
        m.flash = 0.12
        m.tel -= dt
        if m.tel <= 0:  # launch the charge
            dx, dy = _dir_to(gs, m)
            m.vx, m.vy = dx * 320.0, dy * 320.0
            m.charge = 0.55
        return []
    if m.charge > 0:  # sprinting
        m.charge -= dt
        gs.scene.move(m, m.vx * dt, m.vy * dt)
        return _contact_or_cast(gs, m, 1.4)
    _approach(gs, m, m.speed * dt)
    if 120 < _dist(gs, m) < 360 and m.atk_cd <= 0:
        m.atk_cd = 3.0  # charge attempt cooldown
        m.tel = 0.5
        return []
    return _contact_or_cast(gs, m, 1.4)


def _swoop(gs, m, dt: float) -> list[dict]:
    """Cave bat: circles the player, periodically dives at them."""
    m.charge -= dt  # reused as a stable per-bat time phase accumulator
    ang = -m.charge * 1.8 + (sum(map(ord, m.id)) % 10)
    orb_r = 120 + 24 * math.sin(m.charge * 1.3)
    tx = gs.player.x + math.cos(ang) * orb_r
    ty = gs.player.y + math.sin(ang) * orb_r * 0.6
    dx, dy = tx - m.x, ty - m.y
    d = math.hypot(dx, dy) or 1.0
    speed = m.speed * (3.2 if math.sin(m.charge * 0.7) > 0.86 else 1.0)
    gs.scene.move(m, dx / d * speed * dt, dy / d * speed * dt)
    return _contact_or_cast(gs, m, 1.3)


def _caster(gs, m, dt: float) -> list[dict]:
    """Lava imp: keeps firing distance, throws fireballs."""
    d = _dist(gs, m)
    if d < 190:
        _approach(gs, m, -m.speed * dt)   # back away
    elif d > 380:
        _approach(gs, m, m.speed * dt)
    cx, cy = _center(gs, m)
    if d < 460 and m.atk_cd <= 0:
        m.atk_cd = m.ranged.get("cooldown", 2.0)
        speed = m.ranged.get("speed", 260)
        dx, dy = _dir_to(gs, m)
        gs.projectiles.append(Projectile(
            x=cx, y=cy, vx=dx * speed, vy=dy * speed,
            damage=m.attack, range_max=560, kind="ranged",
            sprite=m.ranged.get("sprite", "fireball.png"),
            radius=8.0, friendly=False))
        gs.log(f"{m.name} hurls a fireball!")
    return _contact_or_cast(gs, m, 1.4)


BEHAVIORS = {
    "charger": _charger,
    "swoop": _swoop,
    "caster": _caster,
    "melee": _melee,
}


# ----------------------------------------------------------------- hits
def _hit_player(gs, e) -> list[dict]:
    """One enemy contact hit on the player (thin wrapper over combat)."""
    player_hit(gs, e.attack, e.x, e.y, e.name)
    return []


# ----------------------------------------------------------------- boss hits
def _boss_strike(gs, b) -> list[dict]:
    """Telegraph finished: resolve slam (radius hit) or burst (fireball ring)."""
    if b.tel_name == "slam":
        gs.shake = max(gs.shake, 0.30)
        gs.log(f"{b.name} slams the ground!")
        if math.hypot(gs.player.x - b.x, gs.player.y - b.y) <= b.tel_radius:
            return _hit_player(gs, b)
        return []
    # burst: ring of fireballs around the boss
    n = 10
    for i in range(n):
        ang = 2 * math.pi * i / n
        speed = 200
        gs.projectiles.append(Projectile(
            x=b.x, y=b.y, vx=math.cos(ang) * speed,
            vy=math.sin(ang) * speed,
            damage=b.attack, range_max=420, radius=8.0,
            sprite="fireball.png", friendly=False))
    gs.log(f"{b.name} erupts in flames! (get out of the ring)")
    gs.shake = max(gs.shake, 0.25)
    return []
