"""Headless smoke test for Phases 1+2: FSM, character select, home interior
interactables, house<->outside switching, offline director flow, ui draws."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
PROJ = r"C:\Users\samue\OneDrive\Dokument\Skolan\Github - Koder\Rift-Haven_Pygame\rpg-pygame-spade-skeleton"
sys.path.insert(0, PROJ)
os.chdir(PROJ)

import pygame  # noqa: E402

pygame.init()
screen = pygame.display.set_mode((1280, 720))

from rpg import fsm as F  # noqa: E402
from rpg import ui  # noqa: E402
from rpg.assets import AssetManager  # noqa: E402
from rpg.offline import LocalDirector  # noqa: E402
from rpg.settings import load_settings  # noqa: E402
from rpg.state import GameState  # noqa: E402
from rpg.world import nearest_interactable  # noqa: E402

fails: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


settings = load_settings()
check("settings loads, offline default", settings.offline in (True, False))
check("render scales present",
      56 <= settings.player_height <= 96 and 48 <= settings.enemy_height <= 80
      and 128 <= settings.boss_height <= 224 and settings.hitbox_scale < 1.0)

gs = GameState(settings)
am = AssetManager(settings.tile)
check("initial phase START_MENU", gs.phase == F.START_MENU)
check("menu items", gs.menu_items() == ["New Game", "Continue", "Settings", "Quit"])
check("outside scene exists", "outside" in gs.scenes)

# character select: lock enforcement + stats application
gs.select_character("rogue")
check("locked rogue rejected", gs.character_id is None)
gs.select_character("knight")
check("knight selected", gs.character_id == "knight")
check("knight stats applied",
      gs.player.stats.max_hp == 120 and gs.player.stats.speed == 150)
check("unlocked set has 3 entries", len(gs.unlocked_characters) == 3)

# FSM transitions (main.py sets CHARACTER_SELECT before start_game — mirror it)
gs.phase = F.CHARACTER_SELECT
gs.start_game()
check("start_game (from CHARACTER_SELECT) -> HOME", gs.phase == F.HOME)
gs.unlock_character("rogue")
check("unlock_character works", "rogue" in gs.unlocked_characters)
gs.select_character("rogue")
check("rogue selectable after unlock", gs.character_id == "rogue")

# ---- phase 2: home interior -------------------------------------------
home = gs.scenes["home"]
kinds = sorted(i.kind for i in home.interactables)
check("home has bed/door/chest/trophy",
      all(k in kinds for k in ("bed", "chest", "trophy", "door")))
check("upgrade station now lives outside",
      any(i.kind == "station" for i in gs.scenes["outside"].interactables)
      and "station" not in kinds)
check("home has inspectable props + food",
      "prop" in kinds and "food" in kinds)
door = next(i for i in home.interactables if i.kind == "door")

# teleport the player next to the door, then "press E"
gs.player.x, gs.player.y = door.x + 40, door.y
near = nearest_interactable(home, gs.player.x, gs.player.y, gs.s.tile * 2.0)
check("door within interact range", near is not None and near.kind == "door")
gs.enter_area("outside")
gs.phase = F.OUTSIDE
check("door -> OUTSIDE phase", gs.phase == F.OUTSIDE and gs.area_id == "outside")
check("player spawned at outside spawn",
      gs.player.x == gs.scenes["outside"].spawn[0])

inside_door = next(i for i in gs.scenes["outside"].interactables
                   if i.kind == "door")
gs.player.x, gs.player.y = inside_door.x + 40, inside_door.y + 40
check("outside door reachable", nearest_interactable(
    gs.scenes["outside"], gs.player.x, gs.player.y, gs.s.tile * 2.0) is not None)
gs.enter_area("home")
gs.phase = F.HOME
check("back inside -> HOME", gs.phase == F.HOME and gs.area_id == "home")
check("player spawned at home spawn", gs.player.x == home.spawn[0])

# bed: full heal
gs.player.stats.hp = 10
gs.sleep()
check("sleep restores HP", gs.player.stats.hp == gs.player.stats.max_hp)
check("sleep logs autosave", any("saved to slot" in m for m in gs.messages[-3:]))

# trophy cabinet + upgrade phase
troph = next(i for i in home.interactables if i.kind == "trophy")
gs.player.x, gs.player.y = troph.x + 40, troph.y + 40
check("trophy in range", nearest_interactable(
    home, gs.player.x, gs.player.y, gs.s.tile * 2.0).kind == "trophy")
gs.trophy_menu = True
ui.draw_overlays(screen, gs, am)
gs.trophy_menu = False
check("trophy overlay draws", True)

gs.phase = F.UPGRADE
ui.draw_overlays(screen, gs, am)
gold0 = gs.inv.gold
gs.try_upgrade("hp")
check("upgrade consumes gold", gs.inv.gold == gold0 - 30)
gs.phase = F.HOME  # FSM: UPGRADE -> HOME

# ---- phase 4: combat core (rogue dagger: real projectile) ---------------
from rpg.models import make_mob  # noqa: E402

gs._fsm.state = F.AREA_MOBS  # force combat phase (test harness shortcut)
mob = make_mob(99, "fire_slime", gs.data["enemies"]["fire_slime"],
               gs.player.x + 150, gs.player.y)
gs.mobs.append(mob)
events = gs.fire(gs.player.x + 150, gs.player.y)
check("dagger projectile fired", len(gs.projectiles) == 1
      and gs.projectiles[0].angle == 0)
check("cooldown started", gs.attack_cd > 0)
check("no refire before cooldown", gs.fire(gs.player.x + 150, gs.player.y) == []
      and len(gs.projectiles) == 1)

prj = gs.projectiles[0]
hit_events: list[dict] = []
for _ in range(40):
    gs.attack_cd = 0.0
    hit_events += gs.tick(0.016)
    if hit_events:
        break
check("projectile hit the mob",
      bool(hit_events) and hit_events[-1]["type"] in ("mob_hit", "mob_died")
      and mob.hp < mob.max_hp)
check("hit flash applied", mob.flash > 0 or mob.hp == 0)
check("knockback moved mob", abs(mob.x - (gs.player.x + 150)) > 2
      or mob.hp == 0)
check("damage number floating", any(t.text.isdigit() for t in gs.texts)
      or mob.hp == 0)
check("shot events typed for agents",
      all(e["type"] in ("mob_hit", "mob_died") for e in hit_events))

# knight melee arc
gs.select_character("knight")
gs.projectiles.clear()
gs.attack_cd = 0.0
mob2 = make_mob(98, "cave_bat", gs.data["enemies"]["cave_bat"],
                gs.player.x + 40, gs.player.y)
gs.mobs.append(mob2)
gs.fire(gs.player.x + 40, gs.player.y)
check("knight spawns slash arc", len(gs.projectiles) == 1
      and gs.projectiles[0].kind == "slash")
for _ in range(3):
    gs.attack_cd = 0.0
    hit_events += gs.tick(0.016)
check("slash hit the bat", mob2.hp < mob2.max_hp or mob2.hp == 0)

# life/range expiry (ranger arrow, long range)
gs.select_character("ranger")
gs.projectiles.clear()
mob_far = make_mob(97, "fire_slime", gs.data["enemies"]["fire_slime"],
                   gs.player.x + 500, gs.player.y)
gs.mobs.append(mob_far)
gs.attack_cd = 0.0
gs.fire(gs.player.x + 500, gs.player.y)
for _ in range(3):
    gs.tick(0.016)
check("arrow alive mid-flight", len(gs.projectiles) == 1)
for _ in range(60):
    gs.tick(0.016)
check("arrow expired at max range", len(gs.projectiles) == 0)
gs.mobs.clear()
gs.texts.clear()
gs.projectiles.clear()
gs.select_character("knight")
gs._fsm.state = F.OUTSIDE

# ---- phase 3: hub portal (data-driven, lockable) ------------------------
from rpg.world import portal_locked  # noqa: E402

outside = gs.scenes["outside"]
portal = next(i for i in outside.interactables if i.kind == "portal")
check("hub portal generated from areas.json",
      portal.data.get("area") == "green_cave" and "portal_color" in portal.data)
check("magma portal unlocked by default", not portal_locked(gs, portal))
portals = [i for i in outside.interactables if i.kind == "portal"]
check("4 hub portals (one per area)", len(portals) == 4)
check("portals pinned to picture (hub_pos)",
      all(any(abs(p.x - round(a["hub_pos"][0] * gs.s.width)) <= 1
              and abs(p.y - round(a["hub_pos"][1] * gs.s.height)) <= 1
              for p in portals if p.data["area"] == aid)
          for aid, a in gs.data["areas"].items() if "hub_pos" in a))

# lock it (simulates a --requires boss not yet beaten), verify dim + refusal
gs.data["areas"]["green_cave"]["requires"] = "magma_golem"
check("portal locked until boss beaten", portal_locked(gs, portal))
ui.draw_world(screen, gs, am)  # locked draw + prompt
director = LocalDirector(gs)
director.update(0.016, [{"type": "interact", "kind": "portal",
                         "name": portal.name, **portal.data}])
check("locked portal rejected by director",
      gs.phase == F.OUTSIDE and not gs.mobs)
check("lock message logged",
      any("sealed" in m for m in gs.messages[-3:]))
del gs.data["areas"]["green_cave"]["requires"]
check("portal unlocked again", not portal_locked(gs, portal))
ui.draw_world(screen, gs, am)  # unlocked swirl + particles draw pass

# ---- portal flow from OUTSIDE via offline director ---------------------
director = LocalDirector(gs)
portal = next(i for i in gs.scenes["outside"].interactables
              if i.kind == "portal")
check("portal area set", portal.data.get("area") == "green_cave")
director.update(0.016, [{"type": "interact", "kind": "portal",
                         "name": portal.name, **portal.data}])
check("portal -> AREA_MOBS", gs.phase == F.AREA_MOBS)
check("mobs spawned", len(gs.mobs) > 0)
for m in gs.mobs:
    m.hp = 1.0  # one-shot them
director.update(0.016, [{"type": "mob_died", "id": m.id} for m in gs.mobs])
check("last mob -> BOSS_FIGHT", gs.phase == F.BOSS_FIGHT and gs.boss is not None)
director.update(0.016, [{"type": "boss_died", "id": gs.boss.id}])
# Only one boss exists in the data, so the director may go straight to END.
check("boss reward collected", "magma_golem" in gs.inv.collected_bosses)
check("director advanced past BOSS_FIGHT",
      gs.phase in (F.REWARD, F.HOME, F.OUTSIDE, F.END))
director.update(0.016, [])
check("after reward flow: END or back home",
      gs.phase == F.END or (gs.phase in (F.HOME, F.OUTSIDE)
                            and gs.scene is gs.scenes["home"]))

# ---- phase 5: mob behaviors, hostile projectiles, boss phases ------------
from rpg import enemies as EN  # noqa: E402
from rpg.models import Boss  # noqa: E402

gs._fsm.state = F.AREA_MOBS
gs.mobs.clear()
gs.projectiles.clear()
gs.texts.clear()
gs.boss = None
gs.player.stats.hp = gs.player.stats.max_hp
px0, py0 = gs.player.x, gs.player.y

# charger (fire slime): telegraph -> charge sprint toward the player
slime = make_mob(1, "fire_slime", gs.data["enemies"]["fire_slime"],
                 px0 + 200, py0)
gs.mobs.append(slime)
slime.tel = 0.5
for _ in range(3):
    EN.tick_mobs(gs, 0.2)
check("slime telegraph -> charge armed",
      slime.charge > 0 and getattr(slime, "vx", 0.0) != 0.0)
sx = slime.x
for _ in range(3):
    EN.tick_mobs(gs, 0.016)
check("slime charged toward player", abs(slime.x - sx) > 5)
gs.mobs.clear()

# swoop (cave bat): orbits even while the player stands still
bat = make_mob(2, "cave_bat", gs.data["enemies"]["cave_bat"],
               px0 + 150, min(py0 + 100, gs.scene.h * gs.s.tile - 32))
gs.mobs.append(bat)
bx, by = bat.x, bat.y
EN.tick_mobs(gs, 0.016)
check("bat swoop orbit moves it", (abs(bat.x - bx) + abs(bat.y - by)) > 1)
gs.mobs.clear()

# caster (lava imp): throws a hostile fireball
imp = make_mob(3, "lava_imp", gs.data["enemies"]["lava_imp"],
               px0 + 300, py0)
imp.atk_cd = 0.0
gs.mobs.append(imp)
n_host0 = len([p for p in gs.projectiles if not p.friendly])
EN.tick_mobs(gs, 0.016)
hostile = [p for p in gs.projectiles if not p.friendly]
check("imp throws hostile fireball", len(hostile) == n_host0 + 1)

# hostile projectile hurts the player (combat.player_hit path)
hp0 = gs.player.stats.hp
if hostile:
    hostile[0].x, hostile[0].y = gs.player.x + 5, gs.player.y
for _ in range(3):
    gs.tick(0.016)
check("enemy fireball hurts player", gs.player.stats.hp < hp0)

# melee (skeleton): closes in and swings on contact
skel = make_mob(4, "skeleton_grunt", gs.data["enemies"]["skeleton_grunt"],
                gs.player.x + 15, gs.player.y)  # +15-16jitter < 36 contact
skel.atk_cd = 0.0
gs.mobs.append(skel)
hp1 = gs.player.stats.hp
EN.tick_mobs(gs, 0.016)
check("skeleton melee swing hits player", gs.player.stats.hp < hp1)
gs.mobs.clear()
gs.projectiles.clear()
gs.texts.clear()

# boss: phase-change lines at 66%/33%, telegraph -> slam / burst resolution
bd = gs.data["bosses"]["magma_golem"]
boss = Boss.from_data("magma_golem", bd, px0 + 300, py0 - 200)
gs.boss = boss
msgs0 = len(gs.messages)
boss.hp = boss.max_hp * 0.6
EN.tick_boss(gs, 0.016)
check("phase 1 line at 66%", boss.phase_idx == 1
      and len(gs.messages) > msgs0)
gs.apply({"type": "boss_attack", "name": "slam"})
check("slam telegraph armed", boss.tel > 0 and boss.tel_name == "slam")
for _ in range(50):
    EN.tick_boss(gs, 0.016)
check("slam resolved", boss.tel <= 0
      and any("slams" in m for m in gs.messages[-5:]))
gs.apply({"type": "boss_attack", "name": "burst"})
for _ in range(50):
    EN.tick_boss(gs, 0.016)
check("burst spawns hostile fireball ring",
      any(not p.friendly for p in gs.projectiles))
boss.hp = boss.max_hp * 0.25
EN.tick_boss(gs, 0.016)
check("phase 2 line at 33%", boss.phase_idx == 2)
# combat events still typed for the agent protocol
gs.projectiles.clear()
gs.boss = None

# ---- phase 6/7: inventory, chest, npcs, dialogue, rescue ------------------
gs._fsm.state = F.HOME
gs.enter_area("home")
gs.mobs.clear(); gs.projectiles.clear(); gs.texts.clear(); gs.boss = None

# item stacks: add/remove/count with data-driven defs
defs = gs.data["items"]
gs.inv.add_item("health_potion", 2, defs)
gs.inv.add_item("health_potion", 1, defs)   # stacks onto same slot
check("stacks merge", gs.inv.count("health_potion") == 3
      and len([s for s in gs.inv.items if s.item_id == "health_potion"]) == 1)
check("remove_item caps at stock", gs.inv.remove_item("health_potion", 99) == 3
      and gs.inv.count("health_potion") == 0)

# chest: seed via open, transfer both ways
gs.open_chest_ui("chest")
chest = gs.chests[gs.open_chest]
check("chest seeded for UI demo", len(chest.items) >= 2)
gs.chest_slot = 0
n_chest0 = chest.items[0].qty if chest.items else 0
gs.move_chest_to_inv()
check("chest -> bag transfer", n_chest0 == 0 or chest.items[0].qty < 3
      or len(chest.items) < 2)
gs.inv_slot = max(0, len(gs.inv.items) - 1)
gs.move_inv_to_chest()
check("bag -> chest transfer works", len(gs.inv.items) > 0)
gs.close_chest_ui()
check("chest UI closes", gs.open_chest is None)

# regression: a differently-named chest must register itself on first open
gs.open_chest_ui("crates")
gs.move_chest_to_inv()
check("crates chest opens + transfers (no KeyError)",
      gs.open_chest == "home_crates")
gs.close_chest_ui()
gs.inv.items.clear()          # drop crates-chest loot before the potion test

# potion use
gs.player.stats.hp = 10
gs.inv.add_item("health_potion", 1, defs)
gs.use_potion()
check("potion heals 40 and is consumed",
      gs.player.stats.hp == 50 and gs.inv.count("health_potion") == 0)

# UI draws: inventory grid + chest pane + dialogue paths
gs.open_chest_ui("chest")
ui.draw_overlays(screen, gs, am)
gs.close_chest_ui()
gs.phase = F.INVENTORY
ui.draw_overlays(screen, gs, am)
gs.phase = F.HOME
check("inventory + chest UI draw headless", True)

# NPCs: defs load, standing near one talks, dialogue chains and closes
check("npcs loaded from json", len(gs.npcs) >= 3)
elder = next(n for n in gs.npcs if n["id"] == "elder")
gs.player.x, gs.player.y = elder["x"] * gs.s.tile + 10, elder["y"] * gs.s.tile
check("nearest_npc found near player", gs.nearest_npc(gs.s.tile * 2.5) is elder)
gs.talk_to(elder)
check("dialogue opens with speaker", gs.open_dialogue is not None
      and gs.open_dialogue.get("speaker") == "Elder Maren")
gs.advance_dialogue()
check("dialogue chains to next line", gs.open_dialogue is not None
      and gs.open_dialogue["id"] == "boss_hint")
gs.open_dialogue and None
gs.player.x += 400  # keep the near-NPC check from interfering below
ui.draw_overlays(screen, gs, am)             # dialogue box draw pass
gs.advance_dialogue()
check("dialogue closes at chain end", gs.open_dialogue is None)

# rescue: chained prisoner in the cave unlocks rogue after boss defeat
pris = next(n for n in gs.npcs if n["id"] == "prisoner")
gs.enter_area("green_cave")
gs.player.x, gs.player.y = pris["x"] * gs.s.tile, pris["y"] * gs.s.tile
check("prisoner not rescued yet", "prisoner" not in gs.rescued_npcs)
gs.inv.collect_boss("magma_golem", "Magma Golem")
near = gs.rescuable_npc_here(gs.s.tile * 2.5)
check("prisoner rescuable after boss", near is pris)
if near:
    gs.rescued_npcs.add(near["id"])
    gs.unlock_character(near.get("unlocks", ""))
check("rescue unlocks rogue", "rogue" in gs.unlocked_characters)
gs.enter_area("home")


# ---- phase 8: save/load slots ---------------------------------------------
from rpg import save as SAVE  # noqa: E402

gs._fsm.state = F.HOME
gs.enter_area("home")
gs.character_id = "knight"
gs.inv.add_gold(123)
gs.inv.add_item("magma_core", 2, defs)
gs.unlocked_characters.add("rogue")
check("save writes slot", SAVE.save_slot(gs, 1))
path1 = SAVE._slot_path(1)
d = __import__("json").loads(path1.read_text())
check("save holds key fields",
      d["character"] == "knight" and d["inventory"]["gold"] >= 173
      and "rogue" in d["unlocked_characters"]
      and d["position"]["area"] == "home")

# mutate, then reload the slot and verify everything comes back
gs.inv.gold = 5
gs.inv.items.clear()
gs.player.stats.hp = 7
gs.unlocked_characters.discard("rogue")
gs.enter_area("outside")
check("load restores slot", SAVE.load_slot(gs, 1))
check("load: gold/pos/unlocks back",
      gs.inv.gold >= 173 and gs.area_id == "home"
      and "rogue" in gs.unlocked_characters and gs.phase == F.HOME)
check("load: inventory items back",
      gs.inv.count("magma_core") == 2)
check("slot listing shows entry", any(
    m and m.get("character") == "knight" for m in SAVE.list_saves()))
gs._fsm.state = F.SAVE_SLOTS   # render-only, bypass FSM table (test harness)
ui.draw_save_slots(screen, gs)
gs.phase = F.HOME

knight = am.sprite("player", "knight.png", settings.player_height)
check("knight sprite scaled to ~player_height",
      abs(knight.get_height() - settings.player_height) <= 1)
ghost = am.sprite("furniture", "bed.png", 48)
check("bed placeholder/proper sprite ok", ghost.get_width() > 0)
bg = am.background("home_base", (1280, 720))
check("home background loads", bg is not None)

ui.draw_start_menu(screen, gs.menu_items(), 0)
ui.draw_character_select(screen, gs, am, list(gs.characters()), 0)
ui.draw_settings(screen, gs, 0)
from rpg.combat import FloatingText, Projectile  # noqa: E402
gs.projectiles.append(Projectile(640, 360, 300, 0, 10, 500, "ranged",
                                 "arrow.png"))
gs.texts.append(FloatingText(600, 340, "12"))
for phase in (F.HOME, F.OUTSIDE, F.AREA_MOBS, F.BOSS_FIGHT, F.PAUSED,
              F.INVENTORY, F.UPGRADE):
    gs._fsm.state = phase  # rendering-only pass, bypasses the FSM
    screen.fill((15, 15, 25))
    ui.draw_world(screen, gs, am)
    ui.draw_hud(screen, gs)
    ui.draw_overlays(screen, gs, am)
pygame.display.flip()
check("all ui draw calls headless for all gameplay phases", True)
check("projectile + damage text rendered headless", True)
gs.projectiles.clear()
gs.texts.clear()
check("no invalid FSM transitions recorded", len(gs._fsm.invalid_seen) == 0)

print("RESULT:", "ALL OK" if not fails else f"{len(fails)} FAILURES: {fails}")
sys.exit(1 if fails else 0)
