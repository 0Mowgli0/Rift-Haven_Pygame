"""Save/load: JSON save slots in savegame/ (created on demand).

The save holds: character, stats, inventory (incl. chests), unlocked
characters, rescued NPCs, defeated bosses, position and phase. Saving happens
on: sleeping in the bed, pause-menu "S", pause-menu "H" (Save & Quit) and
autosave after a boss. The game never ends by itself; only Save & Quit ends a
session (spec section 6).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .inventory import ItemStack
from .settings import ROOT

SAVE_DIR = ROOT / "savegame"
SLOTS = 3


def _slot_path(slot: int) -> Path:
    return SAVE_DIR / f"slot{slot}.json"


def list_saves() -> list[dict | None]:
    """Meta info per slot (or None when empty): character, bosses, time."""
    out: list[dict | None] = []
    for i in range(1, SLOTS + 1):
        p = _slot_path(i)
        if p.exists():
            try:
                d = json.loads(p.read_text())
                out.append({"slot": i, "character": d.get("character"),
                            "bosses": len(d.get("trophies", [])),
                            "time": d.get("time", "")})
            except (json.JSONDecodeError, OSError):
                out.append(None)   # corrupt slot: treat as empty
        else:
            out.append(None)
    return out


def to_dict(gs) -> dict:
    """Serialize GameState to a JSON-able dict (pygame thread only)."""
    p = gs.player.stats
    ch = gs.chests.get("home_chest")
    return {
        "character": gs.character_id,
        "stats": {"hp": p.hp, "max_hp": p.max_hp, "attack": p.attack,
                  "defense": p.defense, "speed": p.speed},
        "position": {"area": gs.area_id, "x": gs.player.x, "y": gs.player.y},
        "inventory": gs.inv.to_json(),
        "chest_home": ch.to_json() if ch else [],
        "unlocked_characters": sorted(gs.unlocked_characters),
        "rescued_npcs": sorted(gs.rescued_npcs),
        "time": time.strftime("%Y-%m-%d %H:%M"),
    }


def save_slot(gs, slot: int) -> bool:
    """Write game state to a slot; True on success."""
    try:
        SAVE_DIR.mkdir(exist_ok=True)
        _slot_path(slot).write_text(json.dumps(to_dict(gs), indent=2))
        return True
    except OSError:
        return False


def load_slot(gs, slot: int) -> bool:
    """Restore GameState from a slot; True on success (pygame thread only)."""
    p = _slot_path(slot)
    if not p.exists():
        return False
    try:
        d = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    from . import fsm as F

    cid = d.get("character")
    if cid in gs.data["characters"]:
        if cid not in gs.unlocked_characters:
            gs.unlocked_characters.add(cid)
        gs.select_character(cid)          # applies stats, then overrides:
    st = gs.player.stats
    sd = d.get("stats", {})
    st.max_hp = int(sd.get("max_hp", st.max_hp))
    st.hp = int(sd.get("hp", st.hp))
    st.attack = int(sd.get("attack", st.attack))
    st.defense = int(sd.get("defense", st.defense))
    st.speed = int(sd.get("speed", st.speed))
    inv = d.get("inventory", {})
    gs.inv.load_from(inv, gs.data["items"], gs.data["weapons"])
    gs.chests["home_chest"].items = [
        ItemStack.from_json(x, gs.data["items"]) for x in d.get("chest_home", [])]
    gs.unlocked_characters = set(d.get("unlocked_characters", gs.unlocked_characters))
    gs.rescued_npcs = set(d.get("rescued_npcs", gs.rescued_npcs))
    pos = d.get("position", {})
    gs.enter_area(pos.get("area", "home"))
    gs.player.x = float(pos.get("x", gs.player.x))
    gs.player.y = float(pos.get("y", gs.player.y))
    # Resume in the phase matching where the save was made (town-group
    # areas/stores all come back as TOWN; shops always close on load).
    area = gs.area_id
    gs.phase = (F.HOME if area == "home"
                else F.OUTSIDE if area == "outside" else F.TOWN)
    return True
