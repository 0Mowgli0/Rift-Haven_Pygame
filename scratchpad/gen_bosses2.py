"""Generates the three new boss sprites (Frost Titan, Moss Ancient, Void Warden).

Same hand-drawn pixel-map style as gen_assets.py: small logical grid, x6
upscale, 1px outline. Run from the skeleton dir with the dummy video driver.
"""

import pygame

pygame.init()
pygame.display.set_mode((1, 1))

OUTLINE = (30, 26, 34)


def save(surf, relpath):
    pygame.image.save(surf, relpath)
    print("wrote", relpath, surf.get_size())


def draw_pixels(rows, palette, scale=6, outline=True):
    h, w = len(rows), len(rows[0])
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        assert len(row) == w, row
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            pygame.draw.rect(surf, palette.get(ch, (255, 0, 255)),
                             (x * scale, y * scale, scale, scale))
    if outline:
        mask = pygame.mask.from_surface(surf, 127)
        pygame.draw.polygon(surf, OUTLINE, mask.outline(), 1)
    return surf


FROST_TITAN = (
    [
        "......WW......",
        ".....WHHW.....",
        "....WHHHHW....",
        "...HWWWWWWH...",
        "...WSSSSSSW...",
        "...WSKSSKSW...",
        "...WSSSSSSW...",
        "....WSSSSW....",
        "..JJWIIIIWJJ..",
        ".JJJIIIIIIJJJ.",
        ".JJIIIWWIIIJJ.",
        ".JJIIIWWIIIJJ.",
        "..JIIIIIIIIJ..",
        "...IIIIIIII...",
        "...III..III...",
        "...III..III...",
        "...DDD..DDD...",
        "...DDD..DDD...",
        "..KKKK..KKKK..",
    ],
    {"W": (235, 250, 255), "H": (225, 242, 255), "S": (205, 232, 245),
     "J": (130, 185, 220), "I": (170, 215, 240),
     "D": (105, 155, 195), "K": (60, 80, 110),
     "K": (60, 140, 190)})

MOSS_ANCIENT = (
    [
        ".....LMMML.....",
        "...LLMMMMMML...",
        "..LMMMMLMMMML..",
        "..LMMMMMMMMML..",
        "...LLMMMMMML...",
        ".....BB..BB....",
        "....TTTTTT.....",
        "...TTETTETT....",
        "...TTTTTTTT....",
        "...TTTTTTTT....",
        "..TTTTTTTTTT...",
        "..TTTTTTTTTT...",
        "..TTT..TTTTT...",
        ".TTTT..TTTTT...",
        ".TTT....TTTT...",
        ".TTT....TTTT...",
        ".DDD....DDDD...",
    ],
    {"L": (85, 145, 70), "M": (130, 180, 85), "B": (108, 82, 55),
     "T": (128, 96, 60), "E": (255, 200, 80), "D": (85, 62, 40)})

VOID_WARDEN = (
    [
        ".....PPPP......",
        "....PPPPPP.....",
        "...PPPPPPPP....",
        "...PFFFFFFP....",
        "...PFWFFWFP....",
        "....PFFFFP.....",
        "...PPPPPPPP....",
        "..PPPPPPPPPP...",
        ".PPVWPPPPPVPP..",
        ".PPPPPPWPPPPP..",
        ".PVPPPPPPPPVP..",
        ".PPPPVPPPPPPP..",
        "..PPPPPPPPPP...",
        "..PPP....PPP...",
        "..VP......PV...",
        "..VV......VV...",
        "..GG......GG...",
    ],
    {"P": (95, 62, 150), "V": (65, 38, 105), "W": (225, 195, 255),
     "F": (18, 10, 32), "G": (165, 125, 255)})

for fname, (rows, palette) in {
        "frost_titan.png": FROST_TITAN,
        "moss_ancient.png": MOSS_ANCIENT,
        "void_warden.png": VOID_WARDEN}.items():
    save(draw_pixels(rows, palette), f"assets/bosses/{fname}")

print("BOSS SPRITES OK")
