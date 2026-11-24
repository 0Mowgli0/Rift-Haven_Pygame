"""GameState: single source of truth for the game, owned by the pygame thread.

Agent decisions arrive as events through the bridge (online) or from the
offline director; both funnel into GameState.apply(), so thepygame loop and
agents never touch each other's internals directly.
"""

from __future__ import annotations

import random

from . import fsm as F
from . import combat as CB
from . import enemies as EN
from .fsm import FSM
from .inventory import Chest, Inventory, ItemStack
from .models import Boss, Mob, Player, Weapon, make_mob
from .settings import Settings, load_all_data, load_npcs
from .world import Scene, Interactable, area_scene, home_scene, outside_scene

# Canonical phase names live in rpg/fsm.py (shared with the agent FSM).
# Legacy aliases keep older call sites working until SPADE phase 9 cleanup.
MENU = F.START_MENU
HOME_BASE = F.HOME
TELEPORT = F.OUTSIDE
AREA_MOBS, BOSS_FIGHT = F.AREA_MOBS, F.BOSS_FIGHT
REWARD, UPGRADE, GAME_OVER, END = F.REWARD, F.UPGRADE, F.GAME_OVER, F.END
PHASES = F.STATES


class GameState:
    """Everything the renderer needs. Mutated only from the pygame thread."""

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.data = load_all_data()
        self.player = Player(x=200, y=200)
        self.inv = Inventory()
        self._fsm = FSM(F.START_MENU)
        self.character_id: str | None = None
        self.unlocked_characters: set[str] = {
            cid for cid, c in self.data["characters"].items()
            if not c.get("locked")}
        self.area_id = "home"
        self.mobs: list[Mob] = []
        self.boss: Boss | None = None
        # Real-time combat state (owned by the pygame loop, see rpg/combat.py)
        self.projectiles: list[CB.Projectile] = []
        self.texts: list[CB.FloatingText] = []
        self.attack_cd: float = 0.0
        self.shake: float = 0.0
        self.shake_offset: tuple[float, float] = (0.0, 0.0)
        self.messages: list[str] = []  # transient UI log
        self.trophy_menu = False       # trophy cabinet panel open
        self.paused_from: str | None = None  # phase to resume after PAUSED
        # Phase 6: chests + open UI state. The home chest is the storage box.
        self.chests: dict[str, Chest] = {
            "home_chest": Chest("home_chest")}
        self.open_chest: str | None = None   # chest UI currently open, if any
        self.chest_pane = "chest"            # chest | bag (focus in chest UI)
        self.inv_slot = 0                    # selected slot (left column)
        self.chest_slot = 0                  # selected slot (right column)
        self.hover_tip: tuple[int, int] | None = None  # tooltip grid coords
        # Phase 7: NPCs + dialogue, data-driven from data/npcs.json.
        npc_defs, self.dialogue = load_npcs()
        self.npcs = npc_defs
        self.open_dialogue: dict | None = None   # current line dict or None
        self.rescued_npcs: set[str] = set()      # prisoner ids already freed
        # Phase 8: persistence. active_slot = slot used by autosaves.
        from . import save as SAVE
        self._save = SAVE
        self.active_slot = 1
        self.save_mode = "save"              # "save" | "load" (slot picker)
        t = settings.tile
        hub_cols = round(settings.width / t)
        hub_rows = round(settings.height / t)
        hub_px = (settings.width, settings.height)
        self.scenes: dict[str, Scene] = {
            "home": home_scene(hub_cols, hub_rows, t, px=hub_px),
            "outside": outside_scene(hub_cols, hub_rows, t, px=hub_px),
        }
        for akey, a in self.data["areas"].items():
            self.scenes[akey] = area_scene(
                akey, a["name"], a["map"]["w"], a["map"]["h"], t,
                tuple(a.get("color", (60, 90, 60))),
                bg=a.get("background"))
        # One hub portal per area (data-driven; locked until "requires" boss).
        # "hub_pos" pins each portal to its painted swirl in outside_hub.png
        # as (fx, fy) fractions of the screen; unpinned areas spread evenly.
        outside = self.scenes["outside"]
        for i, (aid, a) in enumerate(self.data["areas"].items()):
            fx, fy = a.get("hub_pos", (0.25 + 0.2 * i, 0.5))
            outside.add(Interactable(
                f"portal_{aid}", "portal",
                round(fx * settings.width), round(fy * settings.height),
                {"area": aid, "portal_color": a.get("portal_color",
                                                    (150, 90, 240))}))
        # Starting weapon
        first = next(iter(self.data["weapons"]))
        self.inv.add_or_get_weapon(first, self.data["weapons"][first])
        self.inv.equip(first)

    @property
    def phase(self) -> str:
        """Current FSM state (canonical names in rpg/fsm.py)."""
        return self._fsm.state

    @phase.setter
    def phase(self, new_state: str) -> None:
        """All phase changes go through the FSM transition table."""
        self._fsm.transition(new_state, log=self.log)

    def menu_items(self) -> list[str]:
        """Start menu entries; Continue stays disabled until saves exist."""
        return ["New Game", "Continue", "Settings", "Quit"]

    def characters(self) -> dict[str, dict]:
        return self.data["characters"]

    def select_character(self, cid: str) -> None:
        """Apply a chosen character: id + stats -> Player (pygame thread)."""
        c = self.data["characters"].get(cid)
        if not c:
            self.log(f"Unknown character '{cid}'.")
            return
        if cid not in self.unlocked_characters:
            self.log(f"{c['name']} is locked: {c.get('unlock_hint', '?')}")
            return
        self.character_id = cid
        st = self.player.stats
        cs = c["stats"]
        st.max_hp = st.hp = cs["hp"]
        st.attack, st.defense, st.speed = cs["attack"], cs["defense"], cs["speed"]
        self.log(f"Playing {c['name']} the {c['title']}: {c['attack_style']}.")

    # ------------------------------------------------------------------ menu
    def start_game(self) -> None:
        self.enter_area("home")   # place the player at the home spawn
        self.phase = F.HOME
        self.log("Welcome home! E = interact, ESC/q = quit.")

    def sleep(self) -> None:
        """Bed interaction: full heal + autosave to the active slot."""
        st = self.player.stats
        st.hp = st.max_hp
        ok = self._save.save_slot(self, self.active_slot)
        self.log("You sleep and wake fully restored."
                 + (f" (saved to slot {self.active_slot})" if ok
                    else " (autosave FAILED)"))

    def autosave(self) -> None:
        """Autosave after a boss (also used by SaveAgent online)."""
        if self._save.save_slot(self, self.active_slot):
            self.log(f"Autosaved to slot {self.active_slot}.")

    def eat(self) -> None:
        """Dinner-table interaction: a small heal with no gold cost."""
        st = self.player.stats
        if st.hp >= st.max_hp:
            self.log("You are already full. The stew keeps simmering.")
            return
        st.hp = min(st.max_hp, st.hp + 25)
        self.log("You grab a warm bowl of stew. (+25 HP)")

    def unlock_character(self, cid: str) -> None:
        """Rescue flow (later phase): unlock a locked character."""
        if cid in self.data["characters"]:
            self.unlocked_characters.add(cid)
            self.log(f"Character unlocked: {self.data['characters'][cid]['name']}!")

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
            if self.boss.intro:
                self.log(f"{d['name']}: \"{self.boss.intro}\"")
        elif et == "mob_died":
            for m in self.mobs:
                if m.id == ev["id"]:
                    m.hp = 0
                    self.inv.add_gold(m.gold)
                    # Materials drop so the inventory/chests have real content.
                    drop = {"fire_slime": "slime_gel", "cave_bat": "bat_wing",
                            "skeleton_grunt": "bone_shard",
                            "lava_imp": "imp_ember"}.get(m.kind, "magma_core")
                    self.inv.add_item(drop, 1, self.data["items"])
                    self.log(f"{m.name} defeated (+{m.gold}g, {drop})")
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
            self.autosave()
        elif et == "phase":
            self.phase = ev["phase"]
            if ev.get("area"):
                self.enter_area(ev["area"])
        elif et == "boss_attack":
            # Agent side picked the attack; pygame resolves the telegraph.
            b = self.boss
            if b and b.alive:
                b.tel = 0.7
                b.tel_name = ev["name"]
                b.tel_radius = 130 if ev["name"] == "slam" else 0.0
                self.log(f"{b.name} winds up: {ev['name'].upper()}!")
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
            self.autosave()
        elif et == "message":
            self.log(ev.get("text", ""))

    # ------------------------------------------------------------ player actions
    def enter_area(self, area_id: str) -> None:
        self.area_id = area_id
        self.mobs, self.boss = [], None
        scene = self.scenes.get(area_id)
        if scene is None:  # data-driven area without a prebuilt scene
            a = self.data["areas"][area_id]
            scene = area_scene(area_id, a["name"], a["map"]["w"],
                               a["map"]["h"], self.s.tile,
                               tuple(a.get("color", (60, 90, 60))),
                               bg=a.get("background"))
            self.scenes[area_id] = scene
        sx, sy = scene.spawn or (2.5 * self.s.tile, 2.5 * self.s.tile)
        self.player.x, self.player.y = sx, sy

    def fire(self, tx: float, ty: float) -> list[dict]:
        """Fire the basic attack toward world point (tx, ty); see combat.py."""
        return CB.try_fire(self, tx, ty)

    def tick(self, dt: float) -> list[dict]:
        """One combat frame inside the pygame loop; returns protocol events.

        Order: projectiles/combat, then per-kind mob behaviors, then boss
        (phase transitions + telegraph resolution).
        """
        events = CB.tick(self, dt)
        events += EN.tick_mobs(self, dt)
        events += EN.tick_boss(self, dt)
        return events

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

    # ------------------------------------------------------------------ phase 6
    def chest_for(self, it_name: str) -> Chest:
        """Chest behind an interactable (stable id per scene)."""
        cid = f"{self.area_id}_{it_name}"
        if cid not in self.chests:
            self.chests[cid] = Chest(cid)
        return self.chests[cid]

    def open_chest_ui(self, it_name: str) -> None:
        """Open the chest storage UI next to the player inventory."""
        self.open_chest = f"{self.area_id}_{it_name}"
        self.inv_slot = 0
        self.chest_slot = 0
        chest = self.chests.get(self.open_chest)
        if chest and not chest.items:
            # Seed the home chest with a starter stash so the UI is usable.
            defs = self.data["items"]
            p, c = defs["health_potion"], defs["magma_core"]
            chest.items.append(ItemStack("health_potion", p["name"],
                                         p["kind"], 2, p["sprite"]))
            chest.items.append(ItemStack("magma_core", c["name"],
                                         c["kind"], 1, c["sprite"]))

    def close_chest_ui(self) -> None:
        self.open_chest = None

    def move_inv_to_chest(self) -> None:
        """Transfer one qty from the selected inventory slot to the chest."""
        if self.open_chest is None:
            return
        from .inventory import transfer
        transfer(self.inv.items, self.chests[self.open_chest].items,
                 self.inv_slot, self.data["items"])
        self.inv_slot = min(self.inv_slot,
                            max(0, len(self.inv.items) - 1))

    def move_chest_to_inv(self) -> None:
        """Transfer one qty from the selected chest slot to the inventory."""
        if self.open_chest is None:
            return
        from .inventory import transfer
        transfer(self.chests[self.open_chest].items, self.inv.items,
                 self.chest_slot, self.data["items"])
        self.chest_slot = min(self.chest_slot,
                              max(0, len(self.chests[self.open_chest].items) - 1))

    def use_potion(self) -> None:
        """Consume a health potion from the inventory."""
        if self.inv.count("health_potion") > 0:
            self.inv.remove_item("health_potion")
            st = self.player.stats
            st.hp = min(st.max_hp, st.hp + 40)
            self.log("Potion quaffed: +40 HP.")
        else:
            self.log("No health potions left.")

    def equip_weapon_slot(self, wid: str) -> None:
        """Equip a weapon from the inventory weapons dict."""
        if wid in self.inv.weapons:
            self.inv.equip(wid)
            self.log(f"Equipped {self.inv.weapons[wid].name}.")

    # ------------------------------------------------------------------ phase 7
    def nearest_npc(self, radius: float) -> dict | None:
        """Closest NPC in this scene within `radius` px of the player."""
        p, tx = self.player, self.s.tile
        best, bd = None, radius
        for n in self.npcs:
            if n.get("scene") != self.area_id:
                continue
            nx, ny = n["x"] * tx, n["y"] * tx
            d = ((nx - p.x) ** 2 + (ny - p.y) ** 2) ** 0.5
            if d < bd:
                best, bd = n, d
        return best

    def talk_to(self, npc: dict) -> None:
        """Open a dialogue with an NPC at its first line."""
        first = npc["lines"][0] if npc.get("lines") else ""
        self.start_dialogue(first)

    def start_dialogue(self, line_id: str) -> None:
        line = self.dialogue.get(line_id)
        if line:
            self.open_dialogue = dict(line, id=line_id)
            self.log(f"{line['speaker']}: {line['text']}")
        else:
            self.open_dialogue = {"speaker": "?", "text": "...", "next": ""}

    def advance_dialogue(self) -> None:
        """E/Enter in dialogue: follow the chain, then close.

        Rescue is NOT automatic here: freeing a chained character is an
        explicit E action on the NPC (see main.py / rescuable_npc_here).
        """
        d = self.open_dialogue
        if not d:
            return
        nxt = d.get("next", "")
        self.open_dialogue = None
        if nxt and nxt in self.dialogue:
            self.start_dialogue(nxt)

    def rescuable_npc_here(self, radius: float) -> dict | None:
        """NPC next to the player whose boss is defeated but not rescued."""
        near = self.nearest_npc(radius)
        if (near
                and near.get("id") not in self.rescued_npcs
                and near.get("rescue_after_boss")
                and near["rescue_after_boss"] in self.inv.collected_bosses):
            return near
        return None
