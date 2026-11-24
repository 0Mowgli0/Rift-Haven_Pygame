"""Game-flow FSM skeleton: states, transition table and a small FSM helper.

This module is the single description of the game-flow state machine used by
- the pygame side (GameState.phase is backed by FSM.state), and
- the SPADE PlayerAgent FSMBehaviour (rpg/agents/player_agent.py mirrors the
  same state names; phase 9 removes the duplication).

The pygame loop owns GameState; in offline mode the LocalDirector acts as the
agent side. Both may only move through transitions listed in TRANSITIONS.

Diagram: see README.md ("State machine").
"""

from __future__ import annotations

# States (names shared with the SPADE agent FSM).
START_MENU = "START_MENU"
SETTINGS = "SETTINGS"
CHARACTER_SELECT = "CHARACTER_SELECT"
HOME = "HOME"
OUTSIDE = "OUTSIDE"
AREA_MOBS = "AREA_MOBS"
BOSS_FIGHT = "BOSS_FIGHT"
REWARD = "REWARD"
INVENTORY = "INVENTORY"
UPGRADE = "UPGRADE"
PAUSED = "PAUSED"
GAME_OVER = "GAME_OVER"
END = "END"
SAVE_SLOTS = "SAVE_SLOTS"   # slot picker: saves (from pause) or loads (menu)

STATES = (START_MENU, SETTINGS, CHARACTER_SELECT, HOME, OUTSIDE, AREA_MOBS,
          BOSS_FIGHT, REWARD, INVENTORY, UPGRADE, PAUSED, GAME_OVER, END,
          SAVE_SLOTS)

# Explicit transition table: source -> allowed destinations.
# Triggers (keys/clicks/agent events) are documented in the README diagram.
TRANSITIONS: dict[str, set[str]] = {
    START_MENU: {SETTINGS, CHARACTER_SELECT},
    SETTINGS: {START_MENU, CHARACTER_SELECT},
    CHARACTER_SELECT: {HOME, START_MENU, OUTSIDE},
    # HOME -> AREA_MOBS stays as a fast path (debug/director use); normal
    # play routes HOME -> OUTSIDE -> AREA_MOBS through the hub scene.
    HOME: {OUTSIDE, UPGRADE, INVENTORY, PAUSED, SETTINGS, CHARACTER_SELECT,
           AREA_MOBS},
    OUTSIDE: {AREA_MOBS, HOME, PAUSED, INVENTORY, UPGRADE, CHARACTER_SELECT},
    AREA_MOBS: {BOSS_FIGHT, HOME, GAME_OVER},
    BOSS_FIGHT: {REWARD, GAME_OVER},
    REWARD: {OUTSIDE, HOME, END},
    INVENTORY: {HOME, OUTSIDE, PAUSED},
    UPGRADE: {HOME, OUTSIDE, PAUSED},
    PAUSED: {START_MENU, HOME, OUTSIDE, AREA_MOBS, BOSS_FIGHT, END,
             SAVE_SLOTS, INVENTORY, UPGRADE},
    GAME_OVER: {HOME, START_MENU},
    # Victory screen: Esc returns home to keep exploring post-game.
    END: {HOME, START_MENU},
    SAVE_SLOTS: {START_MENU, HOME, OUTSIDE, AREA_MOBS, BOSS_FIGHT,
                 INVENTORY, UPGRADE},
}


class FSM:
    """Tiny finite-state machine driven by the TRANSITIONS table.

    The skeleton is lenient: an undocumented transition is still applied but
    logged, so prototype features don't hard-crash. TODO(phase 9): make
    invalid transitions raise once agents fully own the flow.
    """

    def __init__(self, initial: str = START_MENU) -> None:
        self.state = initial
        self.invalid_seen: list[tuple[str, str]] = []

    def can(self, new_state: str) -> bool:
        """True if source.state -> new_state is a documented transition."""
        return new_state in TRANSITIONS.get(self.state, set())

    def transition(self, new_state: str, log=None) -> bool:
        """Move to new_state; returns True when it was a documented move."""
        if new_state not in STATES:
            return False
        if new_state == self.state:      # staying put is not a transition
            return True
        ok = self.can(new_state)
        if not ok:
            self.invalid_seen.append((self.state, new_state))
            if log:
                log(f"FSM: non-canonical {self.state} -> {new_state}")
        self.state = new_state
        return ok
