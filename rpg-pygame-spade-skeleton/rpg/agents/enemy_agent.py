"""EnemyAgent: mob AI ticks, boss attack cooldowns, loot drops.

One EnemyAgent instance per running game. It demonstrates:
- PeriodicBehaviour  -> AI tick: move each mob toward the player.
- TimeoutBehaviour   -> boss attack fires when its cooldown elapses.
- CyclicBehaviour    -> listen for spawn/damage requests over XMPP.
- OneShotBehaviour  -> one-off loot drop when a mob dies.
- Template           -> route only "request" performative to the listener.
"""

from __future__ import annotations

import math

import spade
from spade.behaviour import CyclicBehaviour, OneShotBehaviour, \
    PeriodicBehaviour, TimeoutBehaviour

from ..bridge import Bridge
from ..settings import load_all_data
from . import protocol as P

AI_TICK = 0.5       # seconds between mob AI updates
BOSS_CD = 2.5        # boss attack cooldown seconds


class EnemyAgent(spade.agent.Agent):
    """Runs mob/boss intelligence for the current area."""

    def __init__(self, jid: str, password: str, bridge: Bridge) -> None:
        super().__init__(jid, password)
        self.bridge = bridge
        self.data = load_all_data()
        self.active_mobs: list[dict] = []  # mirrors of spawned mobs, "name"
        self.area = ""

    async def setup(self) -> None:
        self.presence.set_available()
        self.add_behaviour(AiTick(self), period=AI_TICK)          # type: ignore
        self.add_behaviour(RequestListener(self), P.t_for("request"))
        # TimeoutBehaviour: starts the boss attack window; re-arms below.


class AiTick(PeriodicBehaviour):
    """PeriodicBehaviour example: mob respawn/AI tick every `period`."""

    def __init__(self, agent: EnemyAgent, period: float) -> None:
        super().__init__(period=period)
        self.agent = agent

    async def run(self) -> None:
        if not self.agent.active_mobs:
            return
        # Push one movement intent per living mob over the bridge; the
        # pygame loop applies them in GameState.apply("enemy_intent").
        for m in self.agent.active_mobs:
            dx = math.sin(hash(m["id"]) % 7) * m["speed"] * 0.2
            dy = math.cos(hash(m["id"]) % 5) * m["speed"] * 0.2
            self.agent.bridge.send_to_game(
                {"type": "enemy_intent", "id": m["id"],
                 "dx": dx, "dy": dy})


class BossAttack(TimeoutBehaviour):
    """TimeoutBehaviour example: boss attacks once the cooldown elapses,
    then re-arms itself with a fresh TimeoutBehaviour."""

    def __init__(self, agent: EnemyAgent, timeout: float, damage: int) -> None:
        super().__init__(timeout=timeout)
        self.agent = agent
        self.damage = damage

    async def run(self) -> None:
        self.agent.bridge.send_to_game(
            {"type": "enemy_attack", "id": "boss", "damage": self.damage})
        # Cooldown over -> re-arm (the FSM/agent would do this when a boss
        # is alive; kept simple here).
        self.agent.add_behaviour(BossAttack(self.agent, BOSS_CD, self.damage))


class DropLoot(OneShotBehaviour):
    """OneShotBehaviour example: one-off gold drop when a mob dies."""

    def __init__(self, agent: EnemyAgent, mob_id: str, gold: int) -> None:
        super().__init__()
        self.agent = agent
        self.mob_id = mob_id
        self.gold = gold

    async def run(self) -> None:
        self.agent.bridge.send_to_game(
            {"type": "message", "text": f"Loot from {self.mob_id}: +{self.gold}g"})


class RequestListener(CyclicBehaviour):
    """CyclicBehaviour: handle spawn / spawn_boss / mob_died requests."""

    def __init__(self, agent: EnemyAgent) -> None:
        super().__init__()
        self.agent = agent

    async def run(self) -> None:
        msg = await self.receive(timeout=5)
        if not msg:
            return
        body = P.parse(msg)
        t = body.get("type")
        if t == "spawn_mobs":
            self.agent.area = body["area"]
            area = self.agent.data["areas"][body["area"]]
            for i in range(body.get("count", 3)):
                kind = area["mobs"][i % len(area["mobs"])]
                d = self.agent.data["enemies"][kind]
                self.agent.active_mobs.append(
                    {"id": f"{kind}_{i}", "name": d["name"],
                     "speed": d["speed"], "gold": d["gold"]})
            self.agent.bridge.send_to_game(
                {"type": "message",
                 "text": f"{len(self.agent.active_mobs)} enemies inbound!"})
        elif t == "spawn_boss":
            bid = body["boss"]
            d = self.agent.data["bosses"][bid]
            self.agent.bridge.send_to_game(
                {"type": "spawn_boss", "area": body["area"], "boss": bid})
            # Start the boss attack cooldown as a TimeoutBehaviour.
            self.agent.add_behaviour(BossAttack(self.agent, BOSS_CD, d["attack"]))
        elif t == "mob_died":
            # One-off loot drop behaviour.
            mid = body.get("id", "?")
            gold = 0
            for m in list(self.agent.active_mobs):
                if m["id"] == mid:
                    gold = m["gold"]
                    self.agent.active_mobs.remove(m)
            self.agent.add_behaviour(DropLoot(self.agent, mid, gold))
