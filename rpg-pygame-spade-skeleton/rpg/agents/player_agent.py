"""PlayerAgent: owns the main game-flow FSM (FSMBehaviour).

The FSM mirrors the GameState phases in rpg/state.py (START_MENU ->
HOME_BASE -> TELEPORT -> AREA_MOBS -> BOSS_FIGHT -> REWARD -> HOME_BASE,
plus UPGRADE, GAME_OVER and END). Input/combat results arrive from the
pygame loop through the thread-safe Bridge; each state decides the next
state and pushes decisions back over the same bridge.
"""

from __future__ import annotations

import spade
from spade.behaviour import (CyclicBehaviour, FSMBehaviour,
                             PeriodicBehaviour, State)

from .. import state as S
from ..bridge import Bridge
from ..settings import load_all_data
from . import protocol as P

AUTOSAVE_EVERY = 30.0  # seconds


class PlayerAgent(spade.agent.Agent):
    """Agent that runs the top-level game flow FSM."""

    def __init__(self, jid: str, password: str, bridge: Bridge,
                 peers: list[str]) -> None:
        super().__init__(jid, password)
        self.bridge = bridge
        self.peers = peers            # other agents' JIDs
        self.data = load_all_data()   # data/*.json content
        self.current_area = "home"

    async def setup(self) -> None:
        """Register behaviours and presence subscriptions."""
        fsm = GameFSM(self)
        self.add_behaviour(fsm)
        # PeriodicBehaviour example: autosave tick.
        self.add_behaviour(Autosave(self.bridge, AUTOSAVE_EVERY))
        # CyclicBehaviour: listen for XMPP messages from other agents.
        self.add_behaviour(InboxListener(self.bridge), P.t_for("inform"))
        self.presence.set_available()
        for peer in self.peers:
            self.presence.subscribe(peer)  # presence/subscription


class GameFSM(FSMBehaviour):
    """Main flow: explicit states + registered transitions.

    States are registered in __init__ (before the behaviour starts), each
    transition is explicit (see TRANSITIONS), matching the README diagram.
    Each state polls bridge events from the pygame loop and calls
    set_next_state(...) when its transition condition fires.
    """

    def __init__(self, agent: PlayerAgent) -> None:
        super().__init__()
        self.bridge = agent.bridge
        for name, cls in STATES.items():
            self.add_state(name, cls(self.bridge, agent),
                           initial=(name == "START_MENU"))
        for src, dst in TRANSITIONS:
            self.add_transition(src, dst)


# ---------------------------------------------------------------------------
class BaseState(State):
    """Shared helpers for all states."""

    def __init__(self, bridge: Bridge, agent: PlayerAgent) -> None:
        super().__init__()
        self.bridge = bridge
        self.agent = agent

    def drain(self) -> list[dict]:
        """Pull all pending events from the pygame loop (thread-safe)."""
        out: list[dict] = []
        while True:
            ev = self.bridge.recv_from_game()
            if ev is None:
                return out
            out.append(ev)

    def to_game(self, ev: dict) -> None:
        self.bridge.send_to_game(ev)


class StartMenuState(BaseState):
    """START/MENU: wait for the start key from pygame."""

    async def run(self) -> None:
        for ev in self.drain():
            if ev.get("type") == "start_game":
                self.to_game({"type": "phase", "phase": S.HOME_BASE})
                self.set_next_state("HOME_BASE")
                return


class HomeBaseState(BaseState):
    """Hub: interactions (upgrade/chest/trophy) and the teleport portal."""

    async def run(self) -> None:
        for ev in self.drain():
            if ev.get("type") != "interact":
                continue
            kind = ev.get("kind")
            if kind == "portal":
                self.agent.current_area = ev.get("area", "home")
                self.set_next_state("TELEPORT")
            elif kind in ("station",):
                self.to_game({"type": "message", "text": "Upgrade menu open."})
                self.set_next_state("UPGRADE")
            elif kind == "chest":
                self.to_game({"type": "message", "text": "Chest: empty (TODO loot)"})
            elif kind == "trophy":
                self.to_game({"type": "message", "text": "Trophy room (see HUD)."})


class TeleportState(BaseState):
    """Open the chosen area and request mob spawns from the game."""

    async def run(self) -> None:
        evs = self.drain()
        if not evs:
            return
        ev = evs[-1]
        area = self.agent.current_area
        if area == "home":  # portal/exit leading back home
            self.to_game({"type": "phase", "phase": S.HOME_BASE, "area": "home"})
            self.set_next_state("HOME_BASE")
            return
        conf = self.agent.data["areas"].get(area)
        if conf is None:
            self.to_game({"type": "message", "text": f"Unknown area {area}"})
            self.set_next_state("HOME_BASE")
            return
        self.to_game({"type": "message", "text": f"Teleporting to {conf['name']}..."})
        self.to_game({"type": "phase", "phase": S.AREA_MOBS, "area": area})
        self.to_game({"type": "spawn_mobs", "area": area,
                      "count": conf.get("mob_count", 3)})
        self.set_next_state("AREA_MOBS")


class AreaMobsState(BaseState):
    """Mob phase ends on the last mob_died result: spawn the boss."""

    async def run(self) -> None:
        cleared = False
        for ev in self.drain():
            if ev.get("type") == "mob_died":
                self.to_game(ev)
                cleared = True
        if cleared:
            area = self.agent.current_area
            boss = self.agent.data["areas"][area]["boss"]
            self.to_game({"type": "spawn_boss", "area": area, "boss": boss})
            self.set_next_state("BOSS_FIGHT")


class BossFightState(BaseState):
    """Boss phase: forward combat results; on boss_died go to REWARD."""

    async def run(self) -> None:
        for ev in self.drain():
            t = ev.get("type")
            if t == "boss_died":
                self.to_game(ev)  # GameState.apply handles collection/weapon drop
                self.set_next_state("REWARD")
                return
            if t == "mob_died":  # safety net
                self.to_game(ev)
            elif t == "player_died":
                self.set_next_state("GAME_OVER")
                return


class RewardState(BaseState):
    """Aftermath: END if all bosses are collected, else back to base."""

    async def run(self) -> None:
        evs = self.drain()
        if not evs:
            return
        ev = evs[-1]
        if ev.get("type") == "continue":
            all_done = set(self.agent.data["bosses"]) <= set(ev.get("collected", []))
            if all_done:
                self.to_game({"type": "phase", "phase": S.END})
                self.set_next_state("END")
            else:
                self.to_game({"type": "phase", "phase": S.HOME_BASE, "area": "home"})
                self.set_next_state("HOME_BASE")


class UpgradeState(BaseState):
    """UPGRADE: costs applied by ShopAgent (or offline equivalent)."""

    async def run(self) -> None:
        for ev in self.drain():
            if ev.get("type") == "close_upgrade":
                self.to_game({"type": "phase", "phase": S.HOME_BASE})
                self.set_next_state("HOME_BASE")
                return


class GameOverState(BaseState):
    """Player died: revive at home base."""

    async def run(self) -> None:
        for ev in self.drain():
            if ev.get("type") == "revive":
                self.to_game({"type": "phase", "phase": S.HOME_BASE, "area": "home"})
                self.set_next_state("HOME_BASE")
                return


class EndState(BaseState):
    """All bosses defeated; terminal."""

    async def run(self) -> None:
        self.drain()


class Autosave(PeriodicBehaviour):
    """PeriodicBehaviour example: autosave every `period` seconds."""

    def __init__(self, bridge: Bridge, period: float) -> None:
        super().__init__(period=period)
        self.bridge = bridge

    async def run(self) -> None:
        self.bridge.send_to_game({"type": "save"})


class InboxListener(CyclicBehaviour):
    """CyclicBehaviour: receive XMPP messages and forward them to the game."""

    def __init__(self, bridge: Bridge) -> None:
        super().__init__()
        self.bridge = bridge

    async def run(self) -> None:
        msg = await self.receive(timeout=5)
        if msg:
            self.bridge.send_to_game(P.parse(msg))


STATES = {
    "START_MENU": StartMenuState,
    "HOME_BASE": HomeBaseState,
    "TELEPORT": TeleportState,
    "AREA_MOBS": AreaMobsState,
    "BOSS_FIGHT": BossFightState,
    "REWARD": RewardState,
    "UPGRADE": UpgradeState,
    "GAME_OVER": GameOverState,
    "END": EndState,
}

# Explicit transitions (source -> destination). Trigger events are the
# conditions inside each state's run(); see the Mermaid diagram in README.
TRANSITIONS = [
    ("START_MENU", "HOME_BASE"),     # start_game
    ("HOME_BASE", "TELEPORT"),       # interact portal
    ("HOME_BASE", "UPGRADE"),       # interact station
    ("TELEPORT", "AREA_MOBS"),      # enter_area (non-home)
    ("TELEPORT", "HOME_BASE"),      # enter_area == home
    ("AREA_MOBS", "BOSS_FIGHT"),    # last mob_died
    ("BOSS_FIGHT", "REWARD"),       # boss_died
    ("BOSS_FIGHT", "GAME_OVER"),    # player hp <= 0
    ("REWARD", "HOME_BASE"),        # continue, bosses remain
    ("REWARD", "END"),              # continue, all bosses collected
    ("UPGRADE", "HOME_BASE"),       # close_upgrade
    ("GAME_OVER", "HOME_BASE"),     # revive
]
