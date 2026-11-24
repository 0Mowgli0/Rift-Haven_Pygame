"""Entry point: pygame rendering/input loop + SPADE (or offline) logic.

Design note (pygame + SPADE integration): SPADE runs on asyncio and needs
its own running event loop; pygame needs a blocking loop on the main
thread. We therefore run the SPADE agents in a background thread with a
dedicated asyncio loop (rpg/agents/runtime.py) and exchange all state via
thread-safe queues (rpg/bridge.py). The pygame loop owns GameState; the
agent side never touches it directly, only sends protocol events.

Run:  python main.py           (offline mode, default)
      python main.py --online  (requires .env with XMPP credentials)
"""

from __future__ import annotations

import argparse

import pygame

from rpg import state as S
from rpg.agents.runtime import AgentThread
from rpg.assets import AssetManager
from rpg.bridge import Bridge
from rpg.offline import LocalDirector
from rpg.settings import Settings, load_settings
from rpg import ui

KEY_UPGRADES = {pygame.K_1: "hp", pygame.K_2: "attack",
                pygame.K_3: "defense", pygame.K_4: "speed"}
WEAPON_KEY = pygame.K_5


def main() -> None:
    ap = argparse.ArgumentParser(description="pygame+SPADE RPG skeleton")
    ap.add_argument("--online", action="store_true",
                    help="run the SPADE agents over XMPP instead of offline")
    args = ap.parse_args()

    settings: Settings = load_settings()
    settings.offline = settings.offline and not args.online
    pygame.init()
    screen = pygame.display.set_mode((settings.width, settings.height))
    pygame.display.set_caption("pygame + SPADE RPG skeleton")
    clock = pygame.time.Clock()
    am = AssetManager(settings.tile)

    from rpg.state import GameState
    gs = GameState(settings)
    bridge = Bridge()

    director: LocalDirector | None = None
    agents: AgentThread | None = None
    if settings.offline:
        director = LocalDirector(gs)
    else:
        agents = AgentThread(settings, bridge)
        agents.start()

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
                if k in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif gs.phase == S.MENU and k == pygame.K_RETURN:
                    intents.append({"type": "start_game"})
                elif gs.phase == S.GAME_OVER and k == pygame.K_RETURN:
                    gs.revive_at_base()
                elif gs.phase == S.REWARD and k == pygame.K_RETURN:
                    intents.append({"type": "continue",
                                    "collected": gs.inv.collected_bosses})
                elif k == pygame.K_u:  # / upgrade menu at base
                    gs.upgrade_menu = not gs.upgrade_menu
                elif gs.upgrade_menu:
                    if k in KEY_UPGRADES:
                        gs.try_upgrade(KEY_UPGRADES[k])
                    elif k == WEAPON_KEY and gs.inv.equipped:
                        gs.try_upgrade(gs.inv.equipped)

        keys = pygame.key.get_pressed()
        spd = gs.player.stats.speed * dt
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if gs.phase not in (S.MENU, S.GAME_OVER, S.END):
            gs.scene.move(gs.player, dx * spd, dy * spd)
        if keys[pygame.K_SPACE]:
            hit = gs.attack_nearby()  # pygame resolves; agents decide flow
            if hit:
                intents.append(hit)

        # interact key E (nearest interactable within 1.5 tiles)
        if keys[pygame.K_e]:
            intents.append({"type": "interact", **nearest_interactable(gs)})

        # ------------------------------------------------ logic (agents)
        if director is not None:
            director.update(dt, intents)
        else:
            for it in intents:          # pygame -> SPADE thread
                bridge.send_to_agents(it)
            while (ev := bridge.recv_from_agents()) is not None:
                gs.apply(ev)            # SPADE thread -> pygame

        # ---------------------------------------------------------- draw
        screen.fill((15, 15, 25))
        ui.draw_world(screen, gs, am)
        ui.draw_hud(screen, gs)
        ui.draw_overlays(screen, gs)
        pygame.display.flip()

    if agents:
        agents.stop()
    pygame.quit()


def nearest_interactable(gs) -> dict:
    """Return kind/area of the interactable closest to the player (<= 1.5 tiles)."""
    best, bd = None, 1e9
    for it in gs.scene.interactables:
        d = ((it.x - gs.player.x) ** 2 + (it.y - gs.player.y) ** 2) ** 0.5
        if d < bd:
            best, bd = it, d
    if best and bd <= gs.s.tile * 1.5:
        return {"kind": best.kind, "name": best.name, **best.data}
    return {"kind": "", "name": ""}


if __name__ == "__main__":
    main()
