"""SPADE runtime: run all agents in a background thread with their own
asyncio event loop, exchanging state with pygame only via the Bridge.

Why a separate thread+loop: SPADE is asyncio-based and owns its event loop;
pygame needs a blocking real-time loop on the main thread. A dedicated
thread keeps both loops independent, and queue.Queue-based messages avoid
shared-memory races without locks everywhere.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

import spade

from ..bridge import Bridge
from ..settings import Settings
from .enemy_agent import EnemyAgent
from .player_agent import PlayerAgent
from .shop_agent import ShopAgent
from .world_agent import WorldAgent


class AgentThread(threading.Thread):
    """Owns the asyncio loop that hosts every SPADE agent."""

    def __init__(self, settings: Settings, bridge: Bridge) -> None:
        super().__init__(daemon=True, name="spade-agents")
        self.s = settings
        self.bridge = bridge
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.agents: dict[str, spade.agent.Agent] = {}

    def run(self) -> None:
        """Thread body: create loop, start agents, run forever."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        j, p = self.s.jids, self.s.passwords
        world = WorldAgent(j["world"], p["world"], self.bridge,
                           enemy_jid=j["enemy"], player_jid=j["player"])
        enemy = EnemyAgent(j["enemy"], p["enemy"], self.bridge)
        shop = ShopAgent(j["shop"], p["shop"], self.bridge, player_jid=j["player"])
        player = PlayerAgent(j["player"], p["player"], self.bridge,
                             peers=[j["world"], j["enemy"], j["shop"]])
        try:
            for a in (world, enemy, shop, player):
                # a.start(auto_register=True) also creates the account on
                # servers that allow in-band registration.
                a.start(auto_register=True)
            self.agents = {"world": world, "enemy": enemy,
                           "shop": shop, "player": player}
            self.loop.run_forever()
        finally:
            for a in self.agents.values():
                a.stop()
            self.loop.close()

    def stop(self) -> None:
        """Stop the agents and quit the loop (called at app shutdown)."""
        if self.loop and self.loop.is_running():
            for a in self.agents.values():
                a.stop()
            self.loop.call_soon_threadsafe(self.loop.stop)
