"""Offline director: mirrors the agent decisions without XMPP.

Lets the skeleton run end-to-end with zero setup (config.yaml offline:true).
It performs the same role as the SPADE agent side: drains pygame intents
from the bridge, pushes decisions back (spawn/phase/reward...). Switch to
offline:false to get the exact same flow driven by PlayerAgent's FSM.
"""

from __future__ import annotations

import random

from .state import GameState
from . import state as S


class LocalDirector:
    """A tiny local 'agent side' for offline play."""

    def __init__(self, gs: GameState) -> None:
        self.gs = gs
        self.pending = 0      # mobs still alive (mirror)
        self.boss_active = False
        self.attack_cd = 0.0

    def update(self, dt: float, intents: list[dict]) -> None:
        """Process pygame intents + boss attack decisions each frame.

        Mob/boss movement and player harm are resolved in the pygame loop
        (rpg/enemies.py + rpg/combat.py); the director only decides
        high-level flow: waves, boss spawns, boss attack picks, rewards.
        """
        gs = self.gs
        for ev in intents:
            t = ev.get("type")
            if t == "start_game":
                gs.start_game()
            elif t == "interact":
                self._interact(ev)
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
        # 'TimeoutBehaviour' analogue: pick a boss attack every
        # 2.5s scaled by the current phase's cooldown multiplier.
        if self.boss_active:
            self.attack_cd += dt
            boss = gs.boss
            if boss and boss.alive and self.attack_cd >= 2.5 * boss.cd_mult():
                self.attack_cd = 0.0
                gs.apply({"type": "boss_attack",
                          "name": random.choice(boss.attack_list())})
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

    def _interact(self, ev: dict) -> None:
        """Local stand-in for WorldAgent: portals spawn waves, exits retreat.

        Bed/door/station/trophy handling is purely view-side in main.py; only
        things the agent side must own (mob waves, boss spawns) come here.
        """
        gs = self.gs
        kind = ev.get("kind")
        if kind == "portal":
            area = ev.get("area", "green_cave")
            conf = gs.data["areas"].get(area)
            if not conf:
                return
            req = conf.get("requires")
            if req and req not in gs.inv.collected_bosses:
                boss_name = gs.data["bosses"].get(req, {}).get("name", req)
                gs.log(f"Portal sealed: defeat {boss_name} first.")
                return
            self.pending = conf.get("mob_count", 3)
            gs.apply({"type": "phase", "phase": S.AREA_MOBS, "area": area})
            gs.apply({"type": "spawn_mobs", "area": area,
                      "count": conf.get("mob_count", 3)})
        elif kind == "exit":
            gs.apply({"type": "phase", "phase": S.HOME_BASE, "area": "home"})
