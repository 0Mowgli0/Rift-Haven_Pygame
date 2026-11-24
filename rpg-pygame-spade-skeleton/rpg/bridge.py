"""Thread-safe bridge between the pygame loop and the SPADE asyncio thread.

pygame owns the main thread and its loop; SPADE agents live in a background
thread with their own asyncio event loop (separate modules in main.py /
agents/runtime.py). Both sides only communicate through these queues, so no
locks are needed elsewhere.
"""

from __future__ import annotations

import queue
from typing import Any

Event = dict[str, Any]  # {"type": ..., **payload}


class Bridge:
    """Two thread-safe queues: pygame -> agents and agents -> pygame."""

    def __init__(self) -> None:
        self.to_game: queue.Queue[Event] = queue.Queue()
        self.to_agents: queue.Queue[Event] = queue.Queue()

    def send_to_agents(self, event: Event) -> None:
        """Called from the pygame thread (input intents, combat results)."""
        self.to_agents.put(event)

    def send_to_game(self, event: Event) -> None:
        """Called from the SPADE thread (spawns, damage ticks, transitions)."""
        self.to_game.put(event)

    def recv_from_agents(self) -> Event | None:
        """Non-blocking drain for the pygame loop; None if empty."""
        try:
            return self.to_agents.get_nowait()
        except queue.Empty:
            return None

    def recv_from_game(self) -> Event | None:
        """Non-blocking drain for the agent-side behaviours."""
        try:
            return self.to_game.get_nowait()
        except queue.Empty:
            return None
