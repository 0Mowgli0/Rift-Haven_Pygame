"""One-off asset generator for Rift Haven (run from the skeleton dir).

Creates, Stardew-inspired:
  assets/npcs/npc_elder.png, npc_blacksmith.png, npc_scout.png, npc_prisoner.png
  assets/furniture/bed.png, door.png, upgrade_station.png, trophy_cabinet.png
  assets/backgrounds/outside_hub.png   (was missing entirely)
  assets/backgrounds/home_base.png     (redrawn to match interactable tiles)

Sprites are hand-drawn pixel art (16x24 logical grid, x4 upscale for NPCs);
backgrounds are procedural 1280x720 paintings with a seeded RNG so they are
stable across regenerations.
"""

import random

import pygame

pygame.init()
pygame.display.set_mode((1, 1))  # headless surface init


def save(surf, relpath):
    pygame.image.save(surf, relpath)
    print("wrote", relpath, surf.get_size())


# ----------------------------------------------------------------- NPCs ----
SKIN = (232, 190, 150)
OUTLINE = (60, 42, 34)

BODY_LEGS = [
    "................",
    "......HHHH......",
    ".....HHHHHH.....",
    "....HHHHHHHH....",
    "....HSSSSSSH....",
    "....HSESSESH....",
    "....HSSSSSSH....",
    ".....SSSSSS.....",
    "......SSSS......",
    "....CCCCCCCC....",
    "...CCCCCCCCCC...",
    "..CCDCCCCCCDCC..",
    "..SSDCCCCCCDSS..",
    "...CCCCCCCCCC...",
    "...AAAAAAAAAA...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCC....CCC...",
    "...DDD....DDD...",
    "...DDD....DDD...",
    "...DDD....DDD...",
    "...EEE....EEE...",
    "................",
    "................",
]

BODY_ROBE = [
    "................",
    "......HHHH......",
    ".....HHHHHH.....",
    "....HHHHHHHH....",
    "....HSSSSSSH....",
    "....HSESSESH....",
    "....HSSSSSSH....",
    ".....SSSSSS.....",
    "......SSSS......",
    "....CCCCCCCC....",
    "...CCCCCCCCCC...",
    "..CCDCCCCDCCC...",
    "..SSDCCCCDSS....",
    "...CCCCCCCC.....",
    "...AAAAAAAAAA...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...CCCCCCCCCC...",
    "...DDD....DDD...",
    "................",
]

NPCS = {
    # grey hair bun, teal robe with golden trim
    "npc_elder.png": (BODY_ROBE, {
        "H": (176, 176, 182), "S": SKIN, "E": (40, 34, 40),
        "C": (86, 132, 158), "D": (60, 96, 120), "A": (218, 178, 84)}),
    # dark hair, red shirt + brown apron
    "npc_blacksmith.png": (BODY_LEGS, {
        "H": (72, 48, 32), "S": (226, 178, 138), "E": (40, 34, 40),
        "C": (168, 68, 48), "D": (104, 70, 42), "A": (70, 50, 36)}),
    # green hood + cloak
    "npc_scout.png": (BODY_LEGS, {
        "H": (58, 116, 62), "S": SKIN, "E": (40, 34, 40),
        "C": (86, 142, 72), "D": (54, 100, 50), "A": (120, 88, 52)}),
    # greasy black hair, grey rags, rope belt
    "npc_prisoner.png": (BODY_LEGS, {
        "H": (40, 36, 38), "S": (214, 178, 146), "E": (40, 34, 40),
        "C": (128, 124, 118), "D": (94, 90, 86), "A": (146, 110, 60)}),
}


def draw_pixels(rows, palette, scale=4, outline=True):
    h, w = len(rows), len(rows[0])
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        assert len(row) == w, row
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            col = palette.get(ch, (255, 0, 255))
            pygame.draw.rect(surf, col,
                             (x * scale, y * scale, scale, scale))
    if outline:  # cheap 1px dark border around the figure silhouette
        mask = pygame.mask.from_surface(surf, 127)
        osurf = mask.outline()
        pygame.draw.polygon(surf, OUTLINE, osurf, 1)
    return surf


for fname, (rows, palette) in NPCS.items():
    save(draw_pixels(rows, palette), f"assets/npcs/{fname}")

# ------------------------------------------------------------ furniture ----
WOOD = (122, 84, 48)
WOOD_D = (86, 58, 34)
WOOD_L = (156, 112, 66)
GOLD = (232, 188, 72)
METAL = (120, 126, 140)
METAL_D = (74, 78, 90)

# Bed: wooden frame, white pillow, warm blanket (48px tall render).
bed = pygame.Surface((76, 48), pygame.SRCALPHA)
pygame.draw.rect(bed, WOOD_D, (0, 6, 76, 40), border_radius=6)       # frame
pygame.draw.rect(bed, WOOD, (3, 9, 70, 34), border_radius=5)         # inner
pygame.draw.rect(bed, (238, 234, 222), (52, 2, 20, 20), border_radius=4)  # pillow
pygame.draw.rect(bed, (96, 130, 178), (6, 22, 64, 18), border_radius=4)   # blanket
pygame.draw.rect(bed, (74, 104, 148), (6, 22, 64, 5))                # fold
pygame.draw.rect(bed, (250, 244, 220), (24, 27, 14, 8))              # sheet
save(bed, "assets/furniture/bed.png")

# Door: plank door with dark frame + handle (64px tall render).
door = pygame.Surface((48, 64), pygame.SRCALPHA)
pygame.draw.rect(door, WOOD_D, (0, 0, 48, 64), border_radius=4)
pygame.draw.rect(door, WOOD, (5, 4, 38, 58), border_radius=3)
for x in (16, 27):  # planks
    pygame.draw.line(door, WOOD_D, (x, 6), (x, 59), 1)
pygame.draw.circle(door, GOLD, (34, 34), 3)
save(door, "assets/furniture/door.png")

# Upgrade station: stone pedestal + anvil with hot glow (96px tall render).
st = pygame.Surface((64, 96), pygame.SRCALPHA)
pygame.draw.rect(st, (96, 92, 104), (10, 62, 44, 30), border_radius=6)  # base
pygame.draw.rect(st, (120, 116, 128), (16, 56, 32, 10), border_radius=4)
pygame.draw.polygon(st, METAL, [(8, 24), (56, 24), (56, 38), (40, 44),
                                (30, 44), (30, 54), (22, 54), (22, 44),
                                (8, 38)])                            # anvil
pygame.draw.rect(st, METAL_D, (24, 44, 4, 12))
pygame.draw.circle(st, (255, 150, 60), (50, 16), 7)                  # hot orb
pygame.draw.circle(st, (255, 220, 120), (50, 16), 3)
save(st, "assets/furniture/upgrade_station.png")

# Trophy cabinet: wood, two shelves, gold cups (48px tall render).
tc = pygame.Surface((48, 48), pygame.SRCALPHA)
pygame.draw.rect(tc, WOOD_D, (0, 0, 48, 48), border_radius=4)
pygame.draw.rect(tc, WOOD, (3, 3, 42, 42), border_radius=3)
for y in (22, 40):
    pygame.draw.line(tc, WOOD_D, (5, y), (43, y), 2)
for cx, cy in ((12, 15), (24, 15), (36, 15), (14, 33), (28, 33)):
    pygame.draw.rect(tc, GOLD, (cx - 3, cy - 4, 6, 6), border_radius=1)
    pygame.draw.rect(tc, (188, 146, 40), (cx - 4, cy + 2, 8, 2))
save(tc, "assets/furniture/trophy_cabinet.png")

# --------------------------------------------------------- backgrounds ----
def grass_base(w, h, rng, base=(98, 158, 70)):
    surf = pygame.Surface((w, h))
    surf.fill(base)
    for _ in range(2600):  # mottled texture
        x, y = rng.randrange(w), rng.randrange(h)
        c = rng.choice([(88, 146, 62), (108, 170, 78), (114, 178, 82),
                        (82, 138, 58)])
        pygame.draw.rect(surf, c, (x, y, rng.randint(3, 9),
                                    rng.randint(2, 5)))
    for _ in range(700):  # grass blades
        x, y = rng.randrange(w), rng.randrange(h)
        pygame.draw.line(surf, (124, 190, 88), (x, y), (x, y - 3))
    return surf


def tree(surf, x, y, rng, s=1.0):
    th = int(26 * s)
    pygame.draw.rect(surf, (96, 66, 40), (x - 4, y - th // 2, 8, th))
    dark, mid, light = (38, 96, 48), (54, 122, 56), (78, 152, 68)
    for dx, dy, r in ((0, -30, 24), (-16, -16, 19), (16, -16, 19),
                      (0, -12, 22)):
        pygame.draw.circle(surf, dark, (int(x + dx * s),
                                        int(y - th // 2 + dy * s)),
                           int(r * s))
    for dx, dy, r in ((-8, -30, 10), (10, -20, 9), (0, -36, 8)):
        pygame.draw.circle(surf, mid, (int(x + dx * s),
                                       int(y - th // 2 + dy * s)),
                           int(r * s))
    pygame.draw.circle(surf, light, (int(x - 6 * s), int(y - th // 2
                                                     - 30 * s)),
                       int(6 * s))


def flowers(surf, rng, n, area):
    x0, y0, w, h = area
    for _ in range(n):
        x, y = rng.randrange(x0, x0 + w), rng.randrange(y0, y0 + h)
        c = rng.choice([(232, 96, 120), (246, 220, 90), (240, 240, 240),
                        (150, 100, 220)])
        pygame.draw.circle(surf, c, (x, y), 2)
        pygame.draw.circle(surf, (250, 250, 160), (x, y), 1)


# ---- outside hub: grass, sandy paths, house, trees, portal platforms ----
rng = random.Random(42)
out = grass_base(1280, 720, rng)
# main horizontal sandy path
for yy in range(280, 440):
    wob = ((yy * 7) % 23 - 11) // 2
    pygame.draw.line(out, (216, 182, 130), (60 + wob, yy),
                     (1220 - wob, yy), 1)
pygame.draw.rect(out, (216, 182, 130), (60, 285, 1160, 130), border_radius=40)
pygame.draw.rect(out, (202, 166, 116), (60, 380, 1160, 24), border_radius=12)
# path to the house door (house at x~650)
pygame.draw.rect(out, (216, 182, 130), (600, 60, 100, 260), border_radius=30)
flowers(out, rng, 130, (60, 80, 500, 130))
flowers(out, rng, 130, (60, 560, 1140, 120))
flowers(out, rng, 60, (80, 450, 260, 100))
# house facade behind the door interactable
hx, hy, hw, hh = 545, 34, 210, 84
pygame.draw.rect(out, (196, 152, 100), (hx, hy, hw, hh))
for x in range(hx + 16, hx + hw, 16):
    pygame.draw.line(out, (168, 126, 80), (x, hy + 4), (x, hy + hh - 4))
pygame.draw.polygon(out, (112, 64, 44),
                    [(hx - 30, hy + 6), (hx + hw + 30, hy + 6),
                     (hx + hw // 2, hy - 34)])
pygame.draw.polygon(out, (92, 50, 36),
                    [(hx + hw + 30, hy + 6), (hx + hw + 20, hy + 6),
                     (hx + hw // 2, hy - 28)])
for wx, wy in ((hx + 28, hy + 26), (hx + hw - 46, hy + 26)):  # windows
    pygame.draw.rect(out, (110, 160, 220), (wx, wy, 20, 20))
    pygame.draw.rect(out, (70, 50, 34), (wx, wy, 20, 20), 2)
    pygame.draw.line(out, (70, 50, 34), (wx + 10, wy), (wx + 10, wy + 20))
# portal platforms (geometry matches _add_hub_portals: (13+7*i)*tile,32)
for i in range(3):
    cx = (13 + 7 * i) * 32
    pygame.draw.ellipse(out, (128, 128, 138), (cx - 78, 372 - 30, 156, 60))
    pygame.draw.ellipse(out, (100, 100, 112), (cx - 78, 372 - 30, 156, 60), 4)
    for ax in (-64, 60):
        pygame.draw.rect(out, (150, 150, 160),
                         (cx + ax, 380, 14, 26), border_radius=4)
# scatter trees around the edges
tree_xs = [x for x in range(60, 1240, 110)
           if not (470 < x < 830)]  # keep house + path clear
for x in tree_xs:
    tree(out, x, 92, rng, rng.uniform(0.85, 1.25))
for x in range(120, 1200, 150):
    tree(out, x, 668, rng, rng.uniform(1.0, 1.4))
for y in (210, 540):
    tree(out, 44, y, rng, rng.uniform(0.9, 1.1))
    tree(out, 1240, y, rng, rng.uniform(0.9, 1.1))
# rocks
for _ in range(26):
    x, y = rng.randrange(80, 1200), rng.randrange(460, 640)
    pygame.draw.ellipse(out, (128, 128, 136), (x, y, rng.randint(10, 22),
                                               rng.randint(7, 12)))
save(out, "assets/backgrounds/outside_hub.png")

# ---- home interior: wood floor, wall band, fireplace, rug, doormat ----
rng = random.Random(7)
home = pygame.Surface((1280, 720))
WALL_TOP = 96
home.fill((196, 150, 98), (0, 0, 1280, WALL_TOP))          # wall siding
for x in range(0, 1280, 16):
    pygame.draw.line(home, (168, 126, 80), (x, 0), (x, WALL_TOP))
pygame.draw.rect(home, (96, 66, 40), (0, WALL_TOP - 8, 1280, 8))  # baseboard
# floor planks
home.fill((206, 158, 102), (0, WALL_TOP, 1280, 720 - WALL_TOP))
for y in range(WALL_TOP, 720, 32):
    pygame.draw.line(home, (166, 120, 74), (0, y), (1280, y), 2)
for r, y0 in enumerate(range(WALL_TOP, 720, 32)):  # staggered seams
    for x in range((r * 90) % 160, 1280, 160):
        pygame.draw.line(home, (180, 132, 82),
                         (x, y0), (x, min(y0 + 32, 720)))
for _ in range(400):  # grain speckle
    x, y = rng.randrange(1280), rng.randrange(WALL_TOP, 720)
    home.set_at((x, y), (188, 140, 88))
# window on the wall
pygame.draw.rect(home, (110, 160, 220), (860, 14, 120, 66))
pygame.draw.rect(home, (104, 70, 42), (856, 10, 128, 74), 6)
pygame.draw.line(home, (104, 70, 42), (920, 10), (920, 84), 4)
# small painting
pygame.draw.rect(home, (208, 176, 96), (240, 18, 90, 60), 4)
pygame.draw.circle(home, (96, 130, 178), (268, 48), 12)
pygame.draw.polygon(home, (96, 130, 178), [(292, 62), (312, 34), (322, 62)])
# fireplace (right)
pygame.draw.rect(home, (128, 124, 134), (1050, 0, 200, 40))
pygame.draw.rect(home, (108, 104, 114), (1064, 24, 172, 150))
pygame.draw.rect(home, (208, 90, 40), (1090, 60, 120, 34))   # mantel ember
pygame.draw.rect(home, (30, 26, 30), (1096, 96, 108, 78))    # firebox
pygame.draw.polygon(home, (250, 150, 50),
                    [(1116, 170), (1130, 126), (1142, 156), (1152, 118),
                     (1166, 170)])
pygame.draw.polygon(home, (255, 220, 120),
                    [(1126, 170), (1136, 140), (1146, 170)])
# big teal rug with gold diamonds
rug = pygame.Rect(600, 320, 500, 260)
pygame.draw.rect(home, (46, 118, 138), rug, border_radius=12)
pygame.draw.rect(home, (222, 186, 84), rug, 4, border_radius=12)
for i in range(6):
    cx = rug.left + 62 + i * 76
    cy = rug.centery
    pygame.draw.polygon(home, (222, 186, 84),
                        [(cx, cy - 14), (cx + 12, cy), (cx, cy + 14),
                         (cx - 12, cy)])
# doormat by the interior door (interactable at (w//2)*tile,(h-3)*tile)
pygame.draw.rect(home, (140, 100, 60), (588, 630, 104, 44), border_radius=6)
pygame.draw.rect(home, (112, 78, 44), (588, 630, 104, 44), 2, border_radius=6)
# potted plant corners
for px in (36, 1216):
    pygame.draw.rect(home, (140, 84, 48), (px - 12, 680, 24, 22),
                     border_radius=4)
    pygame.draw.circle(home, (58, 122, 56), (px, 668), 16)
    pygame.draw.circle(home, (82, 150, 70), (px - 8, 660), 9)
save(home, "assets/backgrounds/home_base.png")

print("ASSET GENERATION COMPLETE")
