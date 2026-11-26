"""Central settings and documented assumptions.

ASSUMPTIONS (first version):
- Resolution 1280x720, tile size 32 (player sprite 32x32).
- One home base + one area ("green_cave") with 2 mob types and 1 boss.
- Data files are JSON in data/; drop-in content needs no code changes.
- SPADE agents talk FIPA-ish messages with a JSON body (see agents/protocol.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"


@dataclass
class Settings:
    """Runtime configuration merged from config.yaml, .env and defaults."""

    width: int = 1280
    height: int = 720
    fps: int = 60
    tile: int = 32
    # Stardew-like player frame: one tile wide and two tiles tall.
    player_height: int = 64
    enemy_height: int = 64
    boss_height: int = 192
    hitbox_scale: float = 0.6  # collision box < sprite so movement feels fair
    offline: bool = True
    debug: bool = True
    # Placeholder settings page values (audio binds come with later phases).
    volume: float = 0.7
    fullscreen: bool = False
    difficulty: str = "normal"  # TODO: affect stats only in a later phase
    # XMPP credentials (loaded from .env; NEVER hardcoded).
    jids: dict[str, str] = field(default_factory=dict)
    passwords: dict[str, str] = field(default_factory=dict)
    server: str = ""


def _load_xmpp_env(cfg: Settings) -> None:
    """Fill cfg.jids/passwords from .env.

    Option A (single account): one bare JID for all agents, distinct
    resources (player/world/enemy/shop) so several agents share the account.
    Option B (separate accounts): XMPP_PLAYER, XMPP_WORLD, ... win if set.
    """
    user = os.getenv("XMPP_USER", "")
    server = os.getenv("XMPP_SERVER", "")
    pwd = os.getenv("XMPP_PASSWORD", "")
    roles = ("player", "world", "enemy", "shop", "save")
    for role in roles:
        jid = os.getenv(f"XMPP_{role.upper()}", "")
        p = os.getenv(f"XMPP_{role.upper()}_PASSWORD", "")
        if jid and p:  # Option B: dedicated account per agent
            cfg.jids[role], cfg.passwords[role] = jid, p
        elif user and server and pwd:  # Option A: shared account + resource
            cfg.jids[role] = f"{user}@{server}/{role}"
            cfg.passwords[role] = pwd
    cfg.server = server


def load_settings() -> Settings:
    """Load config.yaml, .env and data files into a Settings object."""
    load_dotenv(ROOT / ".env")
    s = Settings()
    cfg_path = ROOT / "config.yaml"
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text()) or {}
        win = raw.get("window", {})
        s.width = win.get("width", s.width)
        s.height = win.get("height", s.height)
        s.fps = win.get("fps", s.fps)
        s.tile = raw.get("tile", s.tile)
        rnd = raw.get("render", {})
        s.player_height = rnd.get("player_height", s.player_height)
        s.enemy_height = rnd.get("enemy_height", s.enemy_height)
        s.boss_height = rnd.get("boss_height", s.boss_height)
        s.hitbox_scale = rnd.get("hitbox_scale", s.hitbox_scale)
        opt = raw.get("settings", {})
        s.volume = opt.get("volume", s.volume)
        s.fullscreen = opt.get("fullscreen", s.fullscreen)
        s.difficulty = opt.get("difficulty", s.difficulty)
        s.offline = bool(raw.get("offline", s.offline))
        s.debug = bool(raw.get("debug", s.debug))
    _load_xmpp_env(s)
    return s


def load_data(name: str) -> dict:
    """Load a JSON data file (enemies, bosses, weapons, areas)."""
    path = DATA / f"{name}.json"
    return json.loads(path.read_text())


def load_all_data() -> dict[str, dict]:
    """Load every data file once; new content only requires new JSON entries."""
    return {n: load_data(n) for n in
            ("enemies", "bosses", "weapons", "areas", "characters", "items",
             "npcs", "shops")}


def load_npcs() -> tuple[list[dict], dict]:
    """NPC definitions + dialogue lines (data/npcs.json), needed by world+ui."""
    raw = load_data("npcs")
    return raw.get("npcs", []), raw.get("dialogue", {})
