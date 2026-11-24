"""ShopAgent: gold economy, stat/weapon upgrades, weapon unlocks.

The pygame loop sends "upgrade" candidate actions over the bridge; the
ShopAgent validates cost, applies the effect through the shared GameState
API (still via bridge events, never direct mutation) and replies with an
inform message. Uses a CyclicBehaviour listener plus a OneShotBehaviour
for unlocking dropped weapons.
"""

from __future__ import annotations

import spade
from spade.behaviour import CyclicBehaviour, OneShotBehaviour

from ..bridge import Bridge
from ..settings import load_all_data
from . import protocol as P

STAT_COST = 30


class ShopAgent(spade.agent.Agent):
    """Owns upgrade prices; agents and offline mode share the same rules."""

    def __init__(self, jid: str, password: str, bridge: Bridge,
                 player_jid: str) -> None:
        super().__init__(jid, password)
        self.bridge = bridge
        self.player_jid = player_jid
        self.data = load_all_data()

    async def setup(self) -> None:
        self.presence.set_available()
        self.add_behaviour(UpgradeListener(self), P.t_for("request"))


class UpgradeListener(CyclicBehaviour):
    """CyclicBehaviour: validate upgrade requests, answer with inform."""

    def __init__(self, agent: ShopAgent) -> None:
        super().__init__()
        self.agent = agent

    async def run(self) -> None:
        # 1) XMPP upgrades (from the PlayerAgent over the network).
        msg = await self.receive(timeout=1)
        if msg:
            body = P.parse(msg)
            if body.get("type") == "upgrade":
                result = self.price_check(body.get("target", ""))
                await self.send(P.build(
                    str(msg.sender), "inform",
                    {"type": "upgrade_result", **result}))
        # 2) Bridge upgrades (from the pygame loop, same protocol locally).
        ev = self.agent.bridge.recv_from_game()
        if ev and ev.get("type") == "upgrade_check":
            self.agent.bridge.send_to_game(
                {"type": "upgrade_result", **self.price_check(ev.get("target", ""))})

    def price_check(self, target: str) -> dict:
        """Compute cost; the game side spends the gold on success."""
        if target in ("hp", "attack", "defense", "speed"):
            return {"ok": True, "target": target, "cost": STAT_COST}
        if target in self.agent.data["weapons"]:
            # Weapon level cost grows with level; game side owns the level.
            return {"ok": True, "target": target, "cost": 20}
        return {"ok": False, "target": target, "cost": 0}


class UnlockWeapon(OneShotBehaviour):
    """OneShotBehaviour example: unlock a boss-dropped weapon once."""

    def __init__(self, agent: ShopAgent, weapon_id: str, owner: str) -> None:
        super().__init__()
        self.agent = agent
        self.weapon_id = weapon_id
        self.owner = owner

    async def run(self) -> None:
        await self.send(P.build(self.owner, "inform",
                                {"type": "weapon_unlocked",
                                 "weapon": self.weapon_id}))
