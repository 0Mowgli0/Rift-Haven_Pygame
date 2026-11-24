"""GameState: single source of truth for the game, owned by the pygame thread.

Agent decisions arrive as events through the bridge (online) or from the
offline director; both funnel into GameState.apply(), so thepygame loop and
agents never touch each other's internals directly.
"""

from __future__ import annotations

import random

import pygame

from .inventory import Inventory
from .models import Boss, Mob, Player, Weapon, make_mob
from .settings import Settings, load_all_data
from .world import Scene, area_scene, home_scene

# Phases mirror the FSM states in rpg/agents/player_agent.py
MENU, HOME_BASE, TELEPORT, AREA_MOBS, BOSS_FIGHT = "MENU HOME_BASE TELEPORT AREA_MOBS BOSS_FIGHT".split()
REWARD, UPGRADE, GAME_OVER, END = "REWARD UPGRADE GAME_OVER END".split()
PHASES = (MENU, HOME_BASE, TELEPORT, AREA_MOBS, BOSS_FIGHT, REWARD, UPGRADE, GAME_OVER, END)


class GameState:
    """Everything the renderer needs. Mutated only from the pygame thread."""

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.data = load_all_data()
        self.player = Player(x=200, y=200)
        self.inv = Inventory()
        self.phase = MENU
        self.area_id = "home"
        self.mobs: list[Mob] = []
        self.boss: Boss | None = None
        self.messages: list[str] = []  # transient UI log
        self.upgrade_menu = False
        t = settings.tile
        self.scenes: dict[str, Scene] = {
            "home": home_scene(40, 22, t),
        }
        for akey, a in self.data["areas"].items():
            self.scenes[akey] = area_scene(
                akey, a["name"], a["map"]["w"], a["map"]["h"], t,
                tuple(a.get("color", (60, 90, 60))))
        # Starting weapon
        first = next(iter(self.data["weapons"]))
        self.inv.add_or_get_weapon(first, self.data["weapons"][first])
        self.inv.equip(first)

    # ------------------------------------------------------------------ menu
    def start_game(self) -> None:
        self.phase = HOME_BASE
        self.log("Welcome home! E = interact, ESC/q = quit.")

    def log(self, text: str) -> None:
        self.messages.append(text)

    @property
    def scene(self) -> Scene:
        return self.scenes.get(self.area_id) or self.scenes["home"]

    # ------------------------------------------------------------- agents' API
    def apply(self, ev: dict) -> None:
        """Apply one bridge event coming from the agent side (or offline dir).

        This is the counterpart of the XMPP message protocol: agents send
        these same payloads over XMPP, world_agent/shop_agent route them.
        """
        et = ev.get("type")
        if et == "spawn_mobs":
            area = self.data["areas"][ev["area"]]
            for i in range(ev["count"]):
                kind = random.choice(area["mobs"])
                x, y = self.scene.free_spot()
                self.mobs.append(make_mob(i, kind, self.data["enemies"][kind], x, y))
            self.phase = AREA_MOBS
            self.log(f"{len(self.mobs)} mobs appeared!")
        elif et == "spawn_boss":
            bid, d = ev["boss"], self.data["bosses"][ev["boss"]]
            x, y = self.scene.free_spot()
            self.boss = Boss.from_data(bid, d, x, y)
            self.phase = BOSS_FIGHT
            self.log(f"BOSS: {d['name']} attacks!")
        elif et == "mob_died":
            for m in self.mobs:
                if m.id == ev["id"]:
                    m.hp = 0
                    self.inv.add_gold(m.gold)
                    self.log(f"{m.name} defeated (+{m.gold}g)")
            if not any(m.alive for m in self.mobs):
                self.mobs = []
                # WorldAgent (or offline director) decides the next phase.
        elif et == "boss_died":
            if self.boss:
                bid = self.boss.id
                self.inv.collect_boss(bid, self.boss.name)
                self.inv.add_gold(self.boss.gold)
                # Some bosses also drop a weapon.
                wid = self.boss.weapon
                if wid and wid in self.data["weapons"]:
                    w = self.inv.add_or_get_weapon(wid, self.data["weapons"][wid])
                    self.log(f"Boss dropped weapon: {w.name}!")
                self.boss = None
            self.phase = REWARD
            self.log("Boss defeated! Reward collected.")
        elif et == "phase":
            self.phase = ev["phase"]
            if ev.get("area"):
                self.enter_area(ev["area"])
        elif et == "enemy_intent":
            # AI tick from EnemyAgent: move one entity toward the player.
            b = self.boss if ev["id"] == "boss" else next(
                (m for m in self.mobs if m.id == ev["id"]), None)
            if b and b.alive:
                self.scene.move(b, ev["dx"], ev["dy"])
        elif et == "enemy_attack":
            dmg = max(0, ev["damage"] - self.player.stats.defense)
            self.player.stats.hp -= dmg
            self.log(f"Hit for {dmg}!")
            if self.player.stats.hp <= 0:
                self.phase = GAME_OVER
                self.log("You died... returning to base.")
        elif et == "upgrade_result":
            self.log(f"Upgrade: {'OK' if ev['ok'] else 'not enough gold'} "
                     f"({self.inv.gold}g left)")
        elif et == "save":
            self.log("Game autosaved. (TODO: persist to disk)")
        elif et == "message":
            self.log(ev.get("text", ""))

    # ------------------------------------------------------------ player actions
    def enter_area(self, area_id: str) -> None:
        self.area_id = area_id
        self.scenes.setdefault(area_id, self.scenes["home"])
        self.mobs, self.boss = [], None
        px, py = 2.5 * self.s.tile, 2.5 * self.s.tile
        self.player.x, self.player.y = px, py

    def attack_nearby(self) -> dict | None:
        """pygame resolves the hit and reports the result to the agents.

        Returns the result event (caller pushes it to bridge.to_agents).
        """
        p = self.player
        pr = pygame.Rect(p.x - 20, p.y - 20, 40, 40)  # TODO: weapon range
        weapon = self.inv.equipped_weapon()
        dmg = (weapon.total_damage(p.stats.attack) if weapon
               else p.stats.attack) + random.randint(0, 3)
        if self.boss and self.boss.alive and pr.collidepoint(self.boss.x, self.boss.y):
            self.boss.hp -= dmg
            if self.boss.hp <= 0:
                return {"type": "boss_died", "id": self.boss.id,
                        "area": self.area_id}
            return {"type": "boss_hit", "id": self.boss.id, "damage": dmg}
        for m in self.mobs:
            if m.alive and pr.collidepoint(m.x, m.y):
                m.hp -= dmg
                if m.hp <= 0:
                    return {"type": "mob_died", "id": m.id, "area": self.area_id}
                return {"type": "mob_hit", "id": m.id, "damage": dmg}
        return None

    def try_upgrade(self, target: str) -> None:
        """Request an upgrade (agents validate; offline it happens here)."""
        if target in ("hp", "attack", "defense", "speed"):
            cost = 30
            if self.inv.spend(cost):
                self.player.stats.upgrade(target)
                self.log(f"{target} upgraded! (-{cost}g)")
            else:
                self.log("Not enough gold.")
        else:
            w = self.inv.add_or_get_weapon(target, self.data["weapons"][target])
            if self.inv.spend(w.upgrade_cost()):
                w.level += 1
                self.log(f"{w.name} -> level {w.level}!")
            else:
                self.log("Not enough gold.")

    def revive_at_base(self) -> None:
        self.player.stats.hp = self.player.stats.max_hp // 2
        self.enter_area("home")
        self.phase = HOME_BASE
        self.log("You wake up at home base.")

    def all_bosses_down(self) -> bool:
        """End condition: every boss in data/bosses.json is collected."""
        return set(self.inv.collected_bosses) >= set(self.data["bosses"])
