# 2D Top-Down RPG Skeleton — pygame + SPADE

A minimal but *runnable* skeleton: pygame renders and reads input, SPADE agents
(XMPP) own high-level flow decisions and AI ticks. Sprites are loaded through a
central AssetManager and scaled proportionally; missing PNGs draw labeled
placeholders so the game never crashes (see `ASSETS_NEEDED.md`).

## Assumptions (v1)

- Python 3.11+, resolution **1280×720**, tile size **32**; render scales
  (player/enemy/boss heights, hitbox scale) are in the `render:` section of
  `config.yaml`.
- Content: one home base, one area (`green_cave`) with 2 mob types, 1 boss, 1 weapon, upgrade menu.
- SPADE 3.3+ (asyncio-based). XMPP credentials come from `.env` only.
- Agents ↔ game share one Bridge; agents never mutate the pygame state directly.

## Project structure

```
.
├── main.py                # pygame loop + thread wiring (entry point)
├── config.yaml            # window, tile, offline flag, debug
├── .env.example           # XMPP credentials template (copy to .env)
├── requirements.txt
├── data/                  # data-driven content (no code changes needed)
│   ├── enemies.json  bosses.json  weapons.json  areas.json
│   ├── characters.json items.json npcs.json        # npcs incl. dialogue
├── assets/
│   ├── player/ enemies/ bosses/ tiles/ ui/ items/   # drop PNGs here
├── rpg/
│   ├── settings.py        # config/.env loading, ASSUMPTIONS, data loaders
│   ├── assets.py          # AssetManager: PNG or labeled-color fallback
│   ├── models.py          # Stats, Player, Mob, Boss, Weapon, Item
│   ├── inventory.py       # gold, item stacks, weapons, trophies, chests
│   ├── state.py           # GameState: single source of truth (pygame thread)
│   ├── combat.py          # projectiles, damage, HP bars, screen shake
│   ├── enemies.py         # per-frame mob behaviors + boss telegraph resolution
│   ├── save.py            # JSON save slots in savegame/ (3 slots)
│   ├── world.py           # Scene placeholder tilemap + interactables
│   ├── bridge.py          # thread-safe queues pygame <-> SPADE
│   ├── offline.py         # LocalDirector (same flow, no XMPP needed)
│   ├── ui.py              # HUD, overlays (rendering only)
│   └── agents/
│       ├── protocol.py    # message helpers + templates
│       ├── runtime.py     # AgentThread: SPADE in bg thread with own asyncio loop
│       ├── player_agent.py  # PlayerAgent + FSMBehaviour (main flow)
│       ├── world_agent.py   # areas, teleports, spawn orchestration
│       ├── enemy_agent.py   # mobs/bosses AI, attack cooldowns, loot
│       └── shop_agent.py    # upgrades, economy, weapon unlocks
```

## State machine (FSMBehaviour in `rpg/agents/player_agent.py`)

Canonical state names and the transition table live in `rpg/fsm.py` (shared by
the pygame side, which stores its phase there, and the agent FSM). Extra agent
side states (`TELEPORT`) are an alias of `OUTSIDE` on the game side until
phase 9 unifies them.

```mermaid
stateDiagram-v2
    [*] --> START_MENU
    START_MENU --> SETTINGS : Settings
    START_MENU --> CHARACTER_SELECT : New Game
    START_MENU --> [*] : Quit
    SETTINGS --> START_MENU : back
    CHARACTER_SELECT --> HOME : confirm character
    CHARACTER_SELECT --> START_MENU : back
    HOME --> OUTSIDE : door / portal (E)
    HOME --> AREA_MOBS : direct portal (legacy, hub routing lands in phase 3)
    HOME --> CHARACTER_SELECT : change character (later phase)
    HOME --> UPGRADE : station (E) / U
    HOME --> INVENTORY : I
    OUTSIDE --> AREA_MOBS : portal to area (E)
    OUTSIDE --> HOME : return (E)
    OUTSIDE --> INVENTORY : I
    AREA_MOBS --> BOSS_FIGHT : last mob_died -> spawn_boss
    AREA_MOBS --> HOME : retreat via return portal (E)
    BOSS_FIGHT --> REWARD : boss_died (autosaves)
    BOSS_FIGHT --> GAME_OVER : player_died (hp <= 0)
    GAME_OVER --> HOME : revive (Enter)
    INVENTORY --> HOME : close (home)
    INVENTORY --> OUTSIDE : close (outside)
    UPGRADE --> HOME : close (Esc)
    REWARD --> OUTSIDE : continue via portal
    REWARD --> END : all bosses collected
    HOME --> SAVE_SLOTS : pause > S
    PAUSED --> SAVE_SLOTS : S (save) / continues on load
    START_MENU --> SAVE_SLOTS : Continue (load)
    SAVE_SLOTS --> START_MENU : Esc (load mode)
    END --> [*]
```

SPADE's `FSMBehaviour` uses `add_state` / `add_transition` + `set_next_state()`
inside each state's `run()`; the "events" in the diagram are the conditions
checked there. The `TRANSITIONS` list in the code mirrors this diagram exactly.

Advanced SPADE behaviours used where they make sense:

| Behaviour | Where | Purpose |
|---|---|---|
| `FSMBehaviour` | PlayerAgent | main game flow (above) |
| `PeriodicBehaviour` | EnemyAgent `AiTick` | mob AI / movement ticks every 0.5 s |
| `PeriodicBehaviour` |	PlayerAgent `Autosave` | autosave every 30 s |
| `TimeoutBehaviour` | EnemyAgent `BossAttack` | boss attack fires once cooldown elapses, re-arms itself |
| `CyclicBehaviour` | `InboxListener`, world/enemy/shop listeners + bridge polling | receive messages continuously |
| `OneShotBehaviour` | `DropLoot`, `UnlockWeapon` | one-off loot drop / weapon unlock |
| `Template` | all listeners | route by `performative` + `ontology` metadata |
| presence | all agents | `presence.set_available()` + `subscribe(peers)` to track who is online |

## Message protocol (XMPP, JSON body)

Every message: `performative` and `ontology: rpg-skeleton` in metadata, a JSON
body `{"type": ..., **payload}`. Body `type` is checked after `parse()` since
SPADE templates cannot match body contents.

| # | From → To | Performative | Body `type` | Payload | Meaning |
|---|---|---|---|---|---|
| 1 | player → world | request | `enter_area` | `area` | request teleport to an area |
| 2 | world → player | inform | `area_opened` | `area` | area validated/entered |
| 3 | world → enemy | request | `spawn_mobs` | `area`, `count` | spawn the area's mobs |
| 4 | enemy → player | inform | `spawn_boss` (as bridge event) | `area`, `boss` | phase 2 begins |
| 5 | player → enemy | request | `attack` / `mob_died` / `boss_died` | `id`, `damage` | combat resolution from pygame |
| 6 | enemy → player | inform | `enemy_attack` | `damage` | boss/mob hit lands (from TimeoutBehaviour cooldown) |
| 7 | enemy → player | inform | `boss_attack` | `name` (`slam`\|`burst`) | phase-scaled attack pick; pygame resolves the telegraph |
| 8 | player → enemy | inform | `boss_hit` echo | `id`, `damage`, `hp`, `max_hp` | boss hp mirror on the agent side (drives phase scaling) |
| 9 | enemy → player | inform | `enemy_intent` | `id`, `dx`, `dy` | AI movement tick (online mode) |
| 10 | player → shop | request | `upgrade` | `target` (`hp|attack|defense|speed|weapon_id`) | buy an upgrade |
| 11 | shop → player | inform | `upgrade_result` | `ok`, `cost` | upgrade accepted / rejected |
| 12 | shop → player | inform | `weapon_unlocked` | `weapon` | OneShot unlock after boss drop |
| 13 | player → world | inform | `save` | — | autosave marker (bed / pause / boss kill) |

The **same payloads** flow through the local `Bridge` as plain dicts
(`rpg/state.py: GameState.apply`), so online and offline modes stay identical.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py            # offline mode (default in config.yaml): no XMPP needed
python main.py --online   # full multi-agent mode over XMPP
```

Controls: WASD/arrows move, **mouse aims, left click (or Space) attacks**,
`E` interact (bed/door/station/chest/trophy, portals, NPCs), `U` upgrade
station at home, `I` inventory (arrows select, `E` use potion, `W` next
weapon), chest UI: `Tab` switch pane, `E` move item, `Esc` close,
`Esc` pause (`S` save to slot, `H` save & quit to title, `Q` quit without
saving), `Enter` confirm menus. Slots 1-4 are reserved for abilities.
Saving: bed autosave, pause-menu slot save, autosave after each boss;
`Continue` on the title screen loads a slot.

### XMPP credentials

Copy `.env.example` to `.env`. Two supported modes:

- **Single account (easiest):** set `XMPP_USER`, `XMPP_SERVER`, `XMPP_PASSWORD`.
  All four agents connect as `user@server/<role>` (XMPP resources), so one
  Jabber account is enough. Most servers allow multiple resources.
- **Separate accounts (cleaner):** set `XMPP_PLAYER`, `XMPP_WORLD`,
  `XMPP_ENEMY`, `XMPP_SHOP` + matching `_PASSWORD` vars; each agent gets its
  own JID (`player@server`, `world@server`, ...). Accounts must already exist
  (SPADE's `start(auto_register=True)` can also try in-band registration).

Set `offline: false` in `config.yaml` (or use `--online`) to enable agents.

### Testing the XMPP connection

```bash
python -c "import asyncio, spade, yaml, os
from dotenv import load_dotenv; load_dotenv()
from rpg.settings import load_settings
async def t():
    s = load_settings()
    a = spade.agent.Agent(s.jids['player'], s.passwords['player'])
    await a.start(auto_register=True)
    print('CONNECTED as', a.jid, '| available:', a.presence.is_available())
    await a.stop()
asyncio.run(t())"
```

Expect `CONNECTED as player@your.server/player`. If your server blocks
multi-resource logins, use separate accounts (Option B).

### How pygame + SPADE coexist

SPADE requires a running asyncio loop; pygame blocks the main thread with its
real-time loop. Solution (`rpg/agents/runtime.py`): agents live in a daemon
`threading.Thread` with `asyncio.new_event_loop()`; `main.py` keeps the pygame
loop on the main thread. All communication goes through two `queue.Queue`s
(`rpg/bridge.py`), so no shared mutable state and no extra locks are needed.
`GameState` is only ever mutated in the pygame thread, via `GameState.apply(event)`.

## How to extend

- **New area:** add an entry to `data/areas.json` (`name`, `mobs`, `mob_count`,
  `boss`, `map`, `background`, `color`, optional `portal_color`; `"requires"`
  names the boss that must fall before its hub portal unlocks). A hub portal
  is generated automatically — no code changes needed — and the return
  portal in each area is always available.
- **New enemy kind / boss:** only `data/enemies.json` / `data/bosses.json`
  (hp, speed, damage, cooldown; bosses may list `phases` and a dropped
  `weapon`) plus a 64x64 sprite in `assets/enemies/` or `assets/bosses/`.
- **New character:** `data/characters.json` (hp/attack/defense/speed, an
  `attack` block with range/cooldown/damage mult, `locked`) + a 64x64 sprite
  in `assets/player/<id>.png`; select screen and unlock flow are data-driven.
- **New FSM state:** add it to the canonical list in `rpg/fsm.py` with its
  transitions, add a matching phase constant in `rpg/state.py` if the game
  side must react, and update the Mermaid diagram above.
- **New NPC + dialogue:** add an entry to `npcs` in `data/npcs.json`
  (`id`, `name`, `sprite`, `scene` + tile `x`/`y`, `lines` listing dialogue
  ids in order) and the dialogue lines under `dialogue` (`speaker`, `text`,
  `next` to chain). A `rescue_after_boss` NPC stands chained in that area,
  shows "Free them!" once its boss is collected, and an `E` press unlocks the
  character named in `unlocks`.
- **New item:** add it to `data/items.json` (`name`, `kind`, `desc`,
  `value`, optional `sprite`); inventories, tooltips and the chest UI pick it
  up with no code changes. Mob material drops are mapped in
  `GameState.apply("mob_died")`.
- **Real art:** any PNG placed in the matching `assets/` subfolder and named
  as in `ASSETS_NEEDED.md` is picked up on the next run; sprites are scaled
  proportionally to the configured render heights (config `render:` section).
  Missing files fall back to labeled colored placeholders automatically.
- **TODO markers** in the code (`# TODO`) show intended places: loot tables,
  tile rendering, save-to-disk, weapon ranges, real tiles.
