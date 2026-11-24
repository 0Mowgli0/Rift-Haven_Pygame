"""Offline director: mirrors the agent decisions without XMPP.

Lets the skeleton run end-to-end with zero setup (config.yaml offline:true).
It performs the same role as the SPADE agent side: drains pygame intents
from the bridge, pushes decisions back (spawn/phase/reward...). Switch to
offline:false to get the exact same flow driven by PlayerAgent's FSM.
"""

from __future__ import annotations

import math
import random

from .models import Mob
from .state import GameState
from . import state as S


class LocalDirector:
    """A tiny local 'agent side' for offline play."""

    def __init__(self, gs: GameState) -> None:
        self.gs = gs
        self.pending = 0      # mobs still alive (mirror)
        self.boss_active = False
        self.tick = 0.0
        self.attack_cd = 0.0

    def update(self, dt: float, intents: list[dict]) -> None:
        """Process pygame intents + simulated behaviours each frame."""
        gs = self.gs
        for ev in intents:
            t = ev.get("type")
            if t == "start_game":
                gs.start_game()
            elif t == "interact" and gs.phase == S.HOME_BASE:
                self._home_interact(ev)
            elif t == "mob_died":
                gs.apply(ev)
                self.pending -= 1
                if self.pending <= 0 and not self.boss_active:
                    bid = gs.data["areas"][gs.area_id]["boss"]
                    gs.apply({"type": "spawn_boss", "area": gs.area_id, "boss": bid})
                    self.boss_active = True
            elif t == "boss_died":
                gs.apply(ev)
                self.boss_active = False
        # 'PeriodicBehaviour' analogue: AI tick every 0.5s.
        self.tick += dt
        if self.tick >= 0.5:
            self.tick = 0.0
            self._ai_tick()
        # 'TimeoutBehaviour' analogue: boss attack every 2.5s.
        if self.boss_active:
            self.attack_cd += dt
            if self.attack_cd >= 2.5:
                self.attack_cd = 0.0
                boss = gs.boss
                if boss and boss.alive:
                    gs.apply({"type": "enemy_attack", "id": "boss",
                              "damage": boss.attack})
        # Death -> GAME_OVER handled inside GameState.apply (enemy_attack).
        if gs.phase == S.GAME_OVER:
            gs.phase = S.HOME_BASE
            gs.revive_at_base()
        if gs.phase == S.REWARD:
            # Auto-continue: back to base, or END when all bosses down.
            if gs.all_bosses_down():
                gs.phase = S.END
            else:
                gs.enter_area("home")
                gs.phase = S.HOME_BASE

    # ------------------------------------------------------------- internals
    def _home_interact(self, ev: dict) -> None:
        gs = self.gs
        kind = ev.get("kind")
        if kind == "portal":
            area = ev.get("area", "green_cave")
            conf = gs.data["areas"].get(area)
            if not conf:
                return
            self.pending = conf.get("mob_count", 3)
            gs.apply({"type": "phase", "phase": S.AREA_MOBS, "area": area})
            gs.apply({"type": "spawn_mobs", "area": area,
                      "count": conf.get("mob_count", 3)})
        elif kind == "chest":
            gs.log("Chest: +20 gold! (TODO: real loot table)")
            gs.inv.add_gold(20)
        elif kind == "trophy":
            gs.log(f"Trophy room: {', '.join(gs.inv.collected_bosses) or 'empty'}")
        elif kind == "exit":
            gs.apply({"type": "phase", "phase": S.HOME_BASE, "area": "home"})

    def _ai_tick(self) -> None:
        """Move living mobs toward the player (EnemyAgent analogue)."""
        gs, p = self.gs, self.gs.player
        for m in gs.mobs:
            if not m.alive:
                continue
            dx, dy = p.x - m.x, p.y - m.y
            d = math.hypot(dx, dy) or 1.0
            step = m.speed * 0.25
            gs.scene.move(m, dx / d * step, dy / d * step)
            if d < 28 and random.random() < 0.4:  # contact attack
                gs.apply({"type": "enemy_attack", "id": m.id, "damage": m.attack})
        boss = gs.boss
        if boss and boss.alive:
            dx, dy = p.x - boss.x, p.y - boss.y
            d = math.hypot(dx, dy) or 1.0
            gs.scene.move(boss, dx / d * boss.speed * 0.15,
                          dy / d * boss.speed * 0.15)
