"""Entry point: pygame rendering/input loop + SPADE (or offline) logic.

Design note (pygame + SPADE integration): SPADE runs on asyncio and needs
its own running event loop; pygame needs a blocking loop on the main thread.
We therefore run the SPADE agents in a background thread with a dedicated
asyncio loop (rpg/agents/runtime.py) and exchange all state via thread-safe
queues (rpg/bridge.py). The pygame loop owns GameState; the agent side never
touches it directly, only sends protocol events.

Phase-2 note: home furniture interactions (bed/door/station/trophy/chest) are
instant view-side actions and run right here; portals/exits stay agent-side
(offline LocalDirector by default, SPADE PlayerAgent flow FSM in --online;
the agent emits "message"/"phase" events that GameState.apply consumes).

Run:  python main.py           (offline mode, default)
      python main.py --online  (requires .env with XMPP credentials)
"""

from __future__ import annotations

import argparse

import pygame

from rpg import ui
from rpg.agents.runtime import AgentThread
from rpg.assets import AssetManager
from rpg.bridge import Bridge
from rpg.offline import LocalDirector
from rpg import fsm as F
from rpg.settings import Settings, load_settings
from rpg.state import GameState
from rpg.world import nearest_interactable, portal_locked

KEY_UPGRADES = {pygame.K_1: "hp", pygame.K_2: "attack",
                pygame.K_3: "defense", pygame.K_4: "speed"}
WEAPON_KEY = pygame.K_5

MENU_ITEMS = ["New Game", "Continue", "Settings", "Quit"]
SETTINGS_ITEMS = ["Volume", "Fullscreen", "Difficulty", "Back"]
DIFFICULTIES = ["easy", "normal", "hard"]
# Phases where the player controls a body in a scene.
GAMEPLAY_PHASES = (F.HOME, F.OUTSIDE, F.TOWN, F.AREA_MOBS, F.BOSS_FIGHT,
                   F.UPGRADE, F.INVENTORY)
# Area id -> phase when arriving through a door/gate (everything else is
# part of the peaceful town group -> TOWN).
_AREA_PHASE = {"home": F.HOME, "outside": F.OUTSIDE}


def main() -> None:
    ap = argparse.ArgumentParser(description="pygame+SPADE RPG")
    ap.add_argument("--online", action="store_true",
                    help="run the SPADE agents over XMPP instead of offline")
    args = ap.parse_args()

    settings = load_settings()
    settings.offline = settings.offline and not args.online
    pygame.init()
    screen = set_mode(settings)
    pygame.display.set_caption("Rift Haven")
    clock = pygame.time.Clock()
    am = AssetManager(settings.tile)

    gs = GameState(settings)
    bridge = Bridge()

    director: LocalDirector | None = None
    agents: AgentThread | None = None
    if settings.offline:
        director = LocalDirector(gs)
    else:
        agents = AgentThread(settings, bridge)
        agents.start()

    menu_idx, settings_idx, char_idx = 0, 0, 0
    char_order = list(gs.characters().keys())
    world_surf = pygame.Surface((settings.width, settings.height))

    running = True
    while running:
        dt = clock.tick(settings.fps) / 1000.0
        intents: list[dict] = []
        # ---------------------------------------------------------- input
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                # -- Esc/Q: contextual (quit / pause / close) -------------
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    if gs.trophy_menu:
                        gs.trophy_menu = False
                    elif gs.phase == F.START_MENU:
                        running = False
                    elif gs.phase == F.PAUSED:
                        gs.phase = gs.paused_from or F.HOME
                    elif gs.phase == F.GAME_OVER:
                        gs.phase = F.START_MENU
                    elif gs.phase == F.END:
                        gs.enter_area("home")   # FSM: END -> HOME
                        gs.phase = F.HOME
                        gs.log("Victory! You return home a hero.")
                    elif gs.phase == F.SHOP:
                        gs.close_shop_ui()
                    elif gs.phase == F.UPGRADE:
                        # Station sits outside; return where the player was.
                        gs.phase = (F.OUTSIDE if gs.area_id == "outside"
                                    else F.HOME)
                    elif gs.phase in GAMEPLAY_PHASES:
                        gs.paused_from = gs.phase
                        gs.phase = F.PAUSED
                    # SETTINGS / CHARACTER_SELECT handle Esc below

                # -- start menu ------------------------------------------
                elif gs.phase == F.START_MENU:
                    menu_idx = _menu_nav(k, menu_idx, len(MENU_ITEMS))
                    if k == pygame.K_RETURN:
                        mk = MENU_ITEMS[menu_idx]
                        if mk == "New Game":
                            gs.phase = F.CHARACTER_SELECT  # via FSM
                            char_idx = 0
                        elif mk == "Continue":
                            gs.save_mode = "load"
                            gs.phase = F.SAVE_SLOTS
                        elif mk == "Settings":
                            gs.phase = F.SETTINGS
                        elif mk == "Quit":
                            running = False

                # -- settings --------------------------------------------
                elif gs.phase == F.SETTINGS:
                    settings_idx = _menu_nav(k, settings_idx,
                                             len(SETTINGS_ITEMS))
                    name = SETTINGS_ITEMS[settings_idx]
                    if k == pygame.K_ESCAPE:
                        gs.phase = F.START_MENU
                    elif k == pygame.K_LEFT or k == pygame.K_RIGHT:
                        _settings_adjust(settings, name, k, DIFFICULTIES)
                        if name == "Fullscreen":
                            screen = set_mode(settings)
                    elif k == pygame.K_RETURN:
                        if name == "Fullscreen":
                            settings.fullscreen = not settings.fullscreen
                            screen = set_mode(settings)
                        elif name == "Back":
                            gs.phase = F.START_MENU

                # -- character select ------------------------------------
                elif gs.phase == F.CHARACTER_SELECT:
                    if k == pygame.K_LEFT:
                        char_idx = (char_idx - 1) % len(char_order)
                    elif k == pygame.K_RIGHT:
                        char_idx = (char_idx + 1) % len(char_order)
                    elif k == pygame.K_RETURN:
                        gs.select_character(char_order[char_idx])
                        if gs.character_id == char_order[char_idx]:
                            gs.start_game()  # FSM: -> HOME
                    elif k == pygame.K_BACKSPACE:
                        gs.phase = F.START_MENU

                # -- paused ----------------------------------------------
                elif gs.phase == F.PAUSED:
                    if k in (pygame.K_RETURN, pygame.K_ESCAPE):
                        gs.phase = gs.paused_from or F.HOME
                    elif k == pygame.K_s:            # save -> slot picker
                        gs.save_mode = "save"
                        gs.phase = F.SAVE_SLOTS
                    elif k == pygame.K_h:            # Save & Quit (ends session)
                        from rpg.save import save_slot
                        save_slot(gs, gs.active_slot)
                        running = False
                    elif k == pygame.K_q:            # quit without saving
                        running = False

                # -- save/load slot picker --------------------------------
                elif gs.phase == F.SAVE_SLOTS:
                    if k == pygame.K_ESCAPE:
                        gs.phase = (F.START_MENU if gs.save_mode == "load"
                                    else (gs.paused_from or F.HOME))
                    elif k in (pygame.K_1, pygame.K_2, pygame.K_3):
                        from rpg.save import list_saves, load_slot, save_slot
                        slot = k - pygame.K_0
                        if gs.save_mode == "save":
                            gs.active_slot = slot
                            save_slot(gs, slot)
                            gs.phase = gs.paused_from or F.HOME
                            gs.paused_from = None
                        else:
                            if load_slot(gs, slot):
                                gs.active_slot = slot
                            elif not any(list_saves()):
                                gs.log("No saves yet - pick New Game.")
                    elif k in (pygame.K_RETURN,):
                        gs.phase = gs.paused_from or F.HOME

                # -- shop trade UI (stock / bag panes) --------------------
                elif gs.phase == F.SHOP:
                    if k in (pygame.K_ESCAPE, pygame.K_q):
                        gs.close_shop_ui()
                    elif k == pygame.K_TAB:
                        gs.shop_pane = ("bag" if gs.shop_pane == "stock"
                                        else "stock")
                        gs.shop_slot = 0
                    elif k == pygame.K_UP or k == pygame.K_DOWN:
                        n = (len(gs.shop_stock()) if gs.shop_pane == "stock"
                             else len(gs.inv.items))
                        if n:
                            gs.shop_slot = (gs.shop_slot
                                            + (-1 if k == pygame.K_UP
                                               else 1)) % n
                    elif k in (pygame.K_e, pygame.K_RETURN):
                        if gs.shop_pane == "stock":
                            gs.buy_from_shop()
                        else:
                            gs.sell_to_shop()

                # -- chest UI (two-pane transfer) --------------------------
                elif gs.open_chest is not None:
                    if k == pygame.K_ESCAPE:
                        gs.close_chest_ui()
                    elif k == pygame.K_TAB:
                        gs.chest_pane = ("bag" if gs.chest_pane == "chest"
                                         else "chest")
                    elif k == pygame.K_LEFT or k == pygame.K_RIGHT:
                        pane = _pane_list(gs)
                        cols = 4
                        gi = gs.chest_slot if gs.chest_pane == "chest" else gs.inv_slot
                        gi = (gi - 1 if k == pygame.K_LEFT else gi + 1) % max(1, len(pane)) \
                            if pane else 0
                        if gs.chest_pane == "chest":
                            gs.chest_slot = gi
                        else:
                            gs.inv_slot = gi
                    elif k == pygame.K_UP or k == pygame.K_DOWN:
                        gi = _pane_idx(gs)
                        cols = 4
                        gi = gi + (-cols if k == pygame.K_UP else cols)
                        gi = max(0, min(gi, len(_pane_list(gs)) - 1 if _pane_list(gs) else 0))
                        _set_pane_idx(gs, gi)
                    elif k == pygame.K_e or k == pygame.K_RETURN:
                        if gs.chest_pane == "chest":
                            gs.move_chest_to_inv()
                        else:
                            gs.move_inv_to_chest()

                # -- dialogue ----------------------------------------------
                elif gs.open_dialogue is not None:
                    if k in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                        gs.advance_dialogue()

                # -- inventory ---------------------------------------------
                elif gs.phase == F.INVENTORY:
                    if k in (pygame.K_i, pygame.K_ESCAPE):
                        gs.phase = (F.HOME if gs.area_id == "home"
                                    else F.OUTSIDE if gs.area_id == "outside"
                                    else F.TOWN)
                    elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP,
                               pygame.K_DOWN):
                        cols, n = 4, len(gs.inv.items)
                        if n:
                            if k == pygame.K_LEFT:
                                gs.inv_slot = (gs.inv_slot - 1) % n
                            elif k == pygame.K_RIGHT:
                                gs.inv_slot = (gs.inv_slot + 1) % n
                            elif k == pygame.K_UP:
                                gs.inv_slot = max(0, gs.inv_slot - cols)
                            else:
                                gs.inv_slot = min(n - 1, gs.inv_slot + cols)
                    elif k == pygame.K_e:
                        gs.use_selected_item()
                    elif k == pygame.K_w:
                        ids = list(gs.inv.weapons)
                        if ids:
                            cur = ids.index(gs.inv.equipped) \
                                if gs.inv.equipped in ids else -1
                            gs.inv.equip(ids[(cur + 1) % len(ids)])
                            gs.log(f"Equipped {gs.inv.equipped_weapon().name}.")

                # -- upgrade station --------------------------------------
                elif gs.phase == F.UPGRADE:
                    if k in KEY_UPGRADES:
                        gs.try_upgrade(KEY_UPGRADES[k])
                    elif k == WEAPON_KEY and gs.inv.equipped:
                        gs.try_upgrade(gs.inv.equipped)
                    # close handled by the Esc branch above

                # -- game over / reward -----------------------------------
                elif gs.phase == F.GAME_OVER and k == pygame.K_RETURN:
                    gs.revive_at_base()
                elif gs.phase == F.REWARD and k == pygame.K_RETURN:
                    intents.append({"type": "continue",
                                    "collected": gs.inv.collected_bosses})

                # -- gameplay --------------------------------------------
                elif k == pygame.K_i and gs.phase in (F.HOME, F.OUTSIDE,
                                                      F.TOWN):
                    gs.phase = F.INVENTORY
                elif k == pygame.K_u and gs.phase == F.OUTSIDE:
                    gs.phase = F.UPGRADE
                elif k in KEY_UPGRADES and gs.phase in (F.AREA_MOBS,
                                                        F.BOSS_FIGHT):
                    gs.log("Ability slot reserved (1-4 wired later).")  # TODO
                elif k == pygame.K_e and gs.phase in (F.HOME, F.OUTSIDE,
                                                      F.TOWN, F.AREA_MOBS):
                    if gs.open_chest is not None or gs.open_dialogue is not None:
                        pass  # UI keys handled above
                    else:
                        # NPCs take priority over furniture when both in range.
                        npc = gs.nearest_npc(gs.s.tile * 3.0)
                        if npc is not None:
                            if gs.rescuable_npc_here(gs.s.tile * 3.0) is npc:
                                gs.rescued_npcs.add(npc["id"])
                                gs.unlock_character(npc.get("unlocks", ""))
                                gs.start_dialogue(
                                    npc["lines"][-1] if npc.get("lines")
                                    else "prisoner_free")
                            elif npc.get("shop"):
                                # Shopkeepers go straight to their trade UI
                                # (greeting lands in the log; E repeats it).
                                gs.open_shop_ui(npc["shop"])
                            else:
                                gs.talk_to(npc)
                        else:
                            it = nearest_interactable(gs.scene, gs.player.x,
                                                      gs.player.y,
                                                      gs.s.tile * 2.0)
                            if it is not None:
                                _handle_interact(gs, it, director, bridge,
                                                 intents)

        keys = pygame.key.get_pressed()
        spd = gs.player.stats.speed * dt
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if gs.phase not in (F.START_MENU, F.SETTINGS, F.CHARACTER_SELECT,
                            F.PAUSED, F.END, F.UPGRADE, F.INVENTORY, F.SHOP) \
                and gs.open_chest is None and gs.open_dialogue is None:
            gs.scene.move(gs.player, dx * spd, dy * spd)
            # Idle-life bookkeeping for the player sprite (see ui.draw_world):
            # reset the idle timer while moving, note last horizontal facing.
            if dx or dy:
                gs.idle_t = 0.0
                if dx:
                    gs.player_face = 1 if dx > 0 else -1
            else:
                gs.idle_t += dt
            # Calm scenes only (no idle glance in the middle of a fight).
            if gs.phase not in (F.HOME, F.OUTSIDE, F.TOWN):
                gs.idle_t = 0.0
        # ---- combat: aim with mouse, shoot with LMB (Space also fires) ----
        if gs.phase in (F.AREA_MOBS, F.BOSS_FIGHT):
            mx, my = pygame.mouse.get_pos()
            attacking = pygame.mouse.get_pressed()[0] or keys[pygame.K_SPACE]
            if attacking:
                intents.extend(gs.fire(mx, my))  # cooldown-aware
        intents.extend(gs.tick(dt))  # projectiles, hits, shake (pygame thread)

        # ------------------------------------------------ logic (agents)
        if director is not None:
            director.update(dt, intents)
        else:
            for it in intents:          # pygame -> SPADE thread
                bridge.send_to_agents(it)
            while (ev := bridge.recv_from_agents()) is not None:
                gs.apply(ev)            # SPADE thread -> pygame

        # ---------------------------------------------------------- draw
        if gs.phase == F.START_MENU:
            ui.draw_start_menu(screen, MENU_ITEMS, menu_idx)
        elif gs.phase == F.SETTINGS:
            ui.draw_settings(screen, gs, settings_idx)
        elif gs.phase == F.CHARACTER_SELECT:
            ui.draw_character_select(screen, gs, am, char_order, char_idx)
        elif gs.phase == F.SAVE_SLOTS:
            world_surf.fill((15, 15, 25))
            ui.draw_world(world_surf, gs, am)
            screen.blit(world_surf, (0, 0))
            ui.draw_save_slots(screen, gs)
        else:
            # World renders into its own surface so screen shake can jitter it.
            world_surf.fill((15, 15, 25))
            ui.draw_world(world_surf, gs, am)
            screen.fill((0, 0, 0))
            screen.blit(world_surf, (int(gs.shake_offset[0]),
                                     int(gs.shake_offset[1])))
            ui.draw_hud(screen, gs)
            ui.draw_overlays(screen, gs, am)
        pygame.display.flip()

    if agents:
        agents.stop()
    pygame.quit()


def _handle_interact(gs: GameState, it, director: LocalDirector | None,
                     bridge: Bridge, intents: list[dict]) -> None:
    """Dispatch one E-press on the nearest interactable.

    View-side interactions (furniture in home) run immediately; area-level
    decisions (portals; exit retreats) go to the agent side / offline
    director through intents.
    """
    kind = it.kind
    if kind in ("door", "gate"):
        # Doors with a "to" destination are view-side teleports: town doors
        # into shops, shop doors back to town, the sign gates, the hub's
        # path to town (and back).
        to = it.data.get("to")
        if to:
            gs.enter_area(to)
            gs.phase = _AREA_PHASE.get(to, F.TOWN)
            gs.log(f"You make your way to the {to.replace('_', ' ')}.")
            return
        # Legacy doors without destination: the home <-> outside pair.
        if gs.phase == F.HOME:
            gs.enter_area("outside")
            gs.phase = F.OUTSIDE
            gs.log("You step outside. The portal waits.")
        else:
            gs.enter_area("home")
            gs.phase = F.HOME
            gs.log("You step back inside.")
    elif kind == "bed":
        gs.sleep()
    elif kind == "station":
        gs.phase = F.UPGRADE
    elif kind == "trophy":
        gs.trophy_menu = not gs.trophy_menu
    elif kind == "chest":
        gs.open_chest_ui(it.name)  # two-pane storage UI (phase 6)
    elif kind == "prop":
        gs.log(it.data.get("text", "Nothing out of the ordinary."))
    elif kind == "food":
        gs.eat()
    elif kind == "portal" and portal_locked(gs, it):
        # Sealed rift: explaining beats a silent refusal.
        req = gs.data["areas"][it.data["area"]].get("requires", "?")
        boss = gs.data["bosses"].get(req, {}).get("name", req)
        gs.log(f"This rift is sealed by riftmagic. "
               f"Defeat the {boss} to open it!")
    else:  # portal / exit: agent-side decision
        intents.append({"type": "interact", "kind": kind, "name": it.name,
                        **it.data})


def _pane_list(gs: GameState) -> list:
    """Items of the focused pane in the chest UI."""
    chest = gs.chests.get(gs.open_chest or "")
    return chest.items if (gs.chest_pane == "chest" and chest) else gs.inv.items


def _pane_idx(gs: GameState) -> int:
    return gs.chest_slot if gs.chest_pane == "chest" else gs.inv_slot


def _set_pane_idx(gs: GameState, gi: int) -> None:
    if gs.chest_pane == "chest":
        gs.chest_slot = gi
    else:
        gs.inv_slot = gi


def set_mode(settings: Settings) -> pygame.Surface:
    """(Re)create the display, honoring the fullscreen setting."""
    if settings.fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode((settings.width, settings.height))


def _menu_nav(k: int, idx: int, count: int) -> int:
    """Common menu navigation; wraps around the list."""
    if k == pygame.K_UP:
        return (idx - 1) % count
    if k == pygame.K_DOWN:
        return (idx + 1) % count
    return idx


def _settings_adjust(settings: Settings, name: str, k: int,
                     difficulties: list[str]) -> None:
    """Left/Right adjustment for one settings row."""
    sign = 1 if k == pygame.K_RIGHT else -1
    if name == "Volume":
        settings.volume = round(min(1.0, max(0.0, settings.volume + sign * 0.1)), 1)
    elif name == "Difficulty":
        i = difficulties.index(settings.difficulty) if \
            settings.difficulty in difficulties else 1
        settings.difficulty = difficulties[(i + sign) % len(difficulties)]


if __name__ == "__main__":
    main()
