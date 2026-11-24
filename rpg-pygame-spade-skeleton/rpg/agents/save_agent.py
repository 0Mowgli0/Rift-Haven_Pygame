"""SaveAgent: persistence over the bridge.

Serialization MUST happen on the pygame thread (GameState is owned there),
so this agent never touches game state: it asks the game to save by sending
a {"type": "save"} bridge event and the pygame side writes the slot
(rpg/save.py). It demonstrates:
- PeriodicBehaviour -> autosave every AUTOSAVE_S seconds,
- CyclicBehaviour   -> manual save requests relayed to the game.
"""

from __future__ import annotations

import spade
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour

from ..bridge import Bridge
from . import protocol as P

AUTOSAVE_S = 30.0


class SaveAgent(spade.agent.Agent):
    """Relays autosave ticks and manual save requests into bridge events."""

    def __init__(self, jid: str, password: str, bridge: Bridge) -> None:
        super().__init__(jid, password)
        self.bridge = bridge

    async def setup(self) -> None:
        self.presence.set_available()
        self.add_behaviour(Autosave(self), period=AUTOSAVE_S)  # type: ignore
        self.add_behaviour(SaveListener(self), P.t_for("request"))


class Autosave(PeriodicBehaviour):
    """Periodically ask the game to autosave to its active slot."""

    def __init__(self, agent: SaveAgent, period: float) -> None:
        super().__init__(period=period)
        self.agent = agent

    async def run(self) -> None:
        self.agent.bridge.send_to_game({"type": "save"})


class SaveListener(CyclicBehaviour):
    """Manual save requests (from the pause menu) come in as requests."""

    def __init__(self, agent: SaveAgent) -> None:
        super().__init__()
        self.agent = agent

    async def run(self) -> None:
        msg = await self.receive(timeout=5)
        if not msg:
            return
        body = P.parse(msg)
        if body.get("type") == "save":
            self.agent.bridge.send_to_game({"type": "save"})
