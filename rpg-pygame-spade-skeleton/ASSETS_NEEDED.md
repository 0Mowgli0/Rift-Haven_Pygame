# ASSETS_NEEDED.md

Assets the game will reference in later phases. Any file listed here that is
missing draws a colored placeholder with a label instead — the game never
crashes, but real art gives the intended look.

Existing assets (already wired in): `assets/player/{knight,mage,rogue,ranger}.png`
(64x64), `assets/enemies/{fire_slime,cave_bat,skeleton_grunt,lava_imp}.png`
(64x64), `assets/bosses/magma_golem.png` (128x128),
`assets/items/{chest_closed,chest_open}.png`,
`assets/backgrounds/{home_base,boss_arena_magma}.png` (1280x720).

All sprites are pixel art; give characters a consistent pixel grid (64x64
source is treated as a character sheet baseline) and transparent backgrounds.
Save files into the folder shown, with exactly these names (the AssetManager
looks them up by name).

## Furniture / home interior (`assets/furniture/`)

| Filename | Size | Description |
|---|---|---|
| upgrade_station.png | 64x96 | Anvil/enchanter pedestal for stat+weapon upgrades, home interior |
| trophy_cabinet.png | 96x48 | Glass display cabinet, front view; empty slots visible so trophy icons can be overlaid |
| bed.png | 96x48 | Simple bed, top-down-ish front view, home interior |
| door.png | 48x64 | Front door of the house, closed |
| door_open.png | 48x64 | Same door, open (used while transitioning) |
| table.png | 64x32 | Small wooden table (decoration) |
| rug.png | 128x64 | Floor rug (decoration, draw under entities) |

## Portals (`assets/effects/`)

Portals are currently drawn procedurally (rotating spiral arms, orbiting
particles, glow) so the game looks right without any files below — drop these
in only if you want sprite-based portals instead:

| Filename | Size | Description |
|---|---|---|
| portal_magma_0..7.png | 6 frames 96x96 | Swirling magma portal, frame animation (orange/red vortex); glow baked into the frame |
| portal_home_0..7.png | 6 frames 96x96 | Blue/white return portal back to the hub |
| portal_locked.png | 96x96 | Dimmed/greyed portal overlay drawn when an area is still locked |
| portal_glow.png | 128x128 | Soft radial glow sprite (additive blend) drawn behind any active portal |

## NPCs (`assets/npcs/`)

| Filename | Size | Description |
|---|---|---|
| npc_elder.png | 64x64 | Standing elder villager, gives lore/hints (home) |
| npc_blacksmith.png | 64x64 | Blacksmith, hints about the upgrade station (home) |
| npc_scout.png | 64x64 | Scout with spyglass, hints about areas/bosses (outside hub) |
| npc_prisoner.png | 64x64 | Locked character in chains, rescued after a boss → unlocks Rogue |

## Projectiles (`assets/projectiles/`)

Combat projectiles are rendered from these files; missing files draw glowing
circle/arc fallbacks, and the knight's slash arc is drawn procedurally
(`slash_arc.png` is optional for a fancier arc):

| Filename | Size | Description |
|---|---|---|
| arrow.png | 32x8 | Ranger arrow, pointing right (rotated to flight direction) |
| plasma_ball.png | 16x16 | Mage plasma ball, blue/orange glowing orb |
| lightning.png | 64x8 | Mage lightning bolt/beam segment (later phase) |
| dagger.png | 16x16 | Rogue throwing dagger, pointing right |
| slash_arc.png | 96x96 | Knight melee swing arc overlay (semi-transparent) |
| fireball.png | 16x16 | Lava imp / boss projectile |

## Effects (`assets/effects/`)

| Filename | Size | Description |
|---|---|---|
| hit_flash.png | 32x32 | White radial flash shown when something takes damage |
| death_puff_0..3.png | 4 frames 32x32 | Small smoke dissolve for enemy deaths |
| spark_0..3.png | 4 frames 16x16 | Hit spark particles (projectile impact) |
| loot_sparkle.png | 24x24 | Twinkle drawn over item drops |
| heal_0..3.png | 4 frames 32x32 | Green sparkle ring (bed rest / healing) |

## UI icons (`assets/ui/`)

| Filename | Size | Description |
|---|---|---|
| trophy_magma_golem.png | 32x32 | Trophy silhouette of the magma golem for the cabinet/UI |
| icon_hp.png | 16x16 | Heart icon (HUD + upgrade menu) |
| icon_attack.png | 16x16 | Sword icon |
| icon_defense.png | 16x16 | Shield icon |
| icon_speed.png | 16x16 | Boot icon |
| icon_gold.png | 16x16 | Coin icon (money) |
| icon_weapon_slot.png | 32x32 | Empty weapon slot frame |
| slot_frame.png | 48x48 | Inventory grid slot frame |
| slot_frame_selected.png | 48x48 | Highlighted slot frame |
| dialog_box.png | 640x128 | Speech box background (9-slice friendly: mostly flat, bordered) |
| cursor_aim.png | 24x24 | Crosshair replacing the mouse cursor in combat |

## Items / materials (`assets/items/`)

| Filename | Size | Description |
|---|---|---|
| magma_core.png | 32x32 | Crafting material dropped by the magma golem |
| health_potion.png | 24x24 | Consumable healing potion |
| key_locked.png | 24x24 | Key/lock icon for locked characters and portals |

## Backgrounds (`assets/backgrounds/`)

| Filename | Size | Description |
|---|---|---|
| outside_hub.png | 1280x720 | Outside scene where the portals stand (later phase) |
| start_menu.png | 1280x720 | Title screen background (optional; gradient fallback exists) |

Priority order for later phases: portals + outside_hub (phase 3),
projectiles + hit_flash (phase 4), fireball + death_puff (phase 5),
trophy icon + slot frames + upgrade station + cabinet (phase 6),
NPCs + dialog_box + npc_prisoner (phase 7).
