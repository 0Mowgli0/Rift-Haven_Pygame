"""WorldAgent: areas, teleports and spawn orchestration.

Receives "enter_area" requests from the PlayerAgent over XMPP, notifies
the game (via the bridge) about the phase change, and asks the EnemyAgent
to spawn the area's mobs. Uses a CyclicBehaviour to listen.
"""

from __future__ import annotations

import spade
from spade.behaviour import CyclicBehaviour

from ..bridge import Bridge
from ..settings import load_all_data
from . import protocol as P


class WorldAgent(spade.agent.Agent):
    """Owns area knowledge (data/areas.json) and teleport validation."""

    def __init__(self, jid: str, password: str, bridge: Bridge,
                 enemy_jid: str, player_jid: str) -> None:
        super().__init__(jid, password)
        self.bridge = bridge
        self.enemy_jid = enemy_jid
        self.player_jid = player_jid
        self.data = load_all_data()

    async def setup(self) -> None:
        self.presence.set_available()
        self.add_behaviour(HandleEnterArea(self), P.t_for("request"))


class HandleEnterArea(CyclicBehaviour):
    """CyclicBehaviour: react to enter_area requests from the player."""

    def __init__(self, agent: WorldAgent) -> None:
        super().__init__()
        self.agent = agent

    async def run(self) -> None:
        msg = await self.receive(timeout=5)
        if not msg:
            return
        body = P.parse(msg)
        if body.get("type") != "enter_area":
            return
        area = body.get("area", "home")
        conf = self.agent.data["areas"].get(area)
        # Inform the game over the bridge (same payload as offline mode).
        self.agent.bridge.send_to_game(
            {"type": "phase",
             "phase": "AREA_MOBS" if conf else "HOME_BASE",
             "area": area if conf else "home"})
        if conf:
            # Ask the EnemyAgent to spawn mobs for this area.
            await self.send(P.build(self.agent.enemy_jid, "request",
                                    {"type": "spawn_mobs", "area": area,
                                     "count": conf.get("mob_count", 3)}))
        await msg.reply(body=json_reply({"type": "area_opened", "area": area}))


def json_reply(body: dict):
    """Small helper to build a reply Message from a dict."""
    import json
    from spade.message import Message
    m = Message()
    m.set_metadata("performative", "inform")
    m.set_metadata("ontology", P.ONTOLOGY)
    m.body = json.dumps(body)
    return m
