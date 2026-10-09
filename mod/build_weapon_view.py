"""Optional: replace Freedoom's first-person weapons and muzzle flashes with hand-built voxel guns.

The default mod keeps Freedoom's own first-person guns (hand-drawn, they read better at Doom's resolution);
this builds weapon_view_voxel.wad for players who want TGMC-coloured guns instead.

The guns are modelled in gun_models.py (stock, receiver, barrel, magazine, sights, grip; sized after the TGMC
icons) and rendered straight ahead from behind and above, with a gloved forearm in each lower corner. Every
Freedoom weapon frame gets the rest pose kicked back and up by a per-frame recoil amount, rendered at the
rest frame's camera framing so the gun does not rescale. Muzzle flash sprites are drawn procedurally and
placed on the muzzle: yellow for the guns, a fireball for the rocket launcher, cyan for plasma, green for the BFG.

usage: build_weapon_view.py --freedoom SPRITES_DIR --playpal IWAD --out WAD   (--sprites/--buildcfg accepted, unused)
"""
import argparse
import glob
import math
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
import gun_models  # noqa: E402

CANVAS = (150, 100)
SCREEN_CENTRE_X = 160           # Doom's weapon layer is drawn on a 320x200 screen
SCREEN_BOTTOM = 200
# weapon prefix -> {frame letter: (recoil back, recoil up)} in voxels; frames not listed use the rest pose
RECOIL = {
    "PISG": {"B": (3, 1.5), "C": (5, 2.5), "D": (2, 1)},
    "SHTG": {"B": (4, 2), "C": (6, 3), "D": (2, 1)},
    "SHT2": {"B": (3, 1), "C": (6, 3), "D": (4, 2), "E": (2, 1), "F": (1, 0), "G": (1, 0), "H": (2, 1), "I": (3, 1.5), "J": (1, 0)},
    "CHGG": {"B": (2, 1)},
    "MISG": {"B": (5, 2)},
    "PLSG": {"B": (3, 1)},
    "BFGG": {"B": (2, 1), "C": (5, 2)},
    "SAWG": {"B": (0, 1), "C": (1, 0), "D": (0, 1)},
}
# flash sprite prefix -> (weapon prefix, kind)
FLASHES = {"PISF": ("PISG", "gun_small"), "SHTF": ("SHTG", "gun_big"), "CHGF": ("CHGG", "gun_mid"),
           "MISF": ("MISG", "missile"), "PLSF": ("PLSG", "plasma"), "BFGF": ("BFGG", "bfg")}

PALETTES = {
    "gun": [(255, 252, 214), (255, 226, 110), (255, 160, 44), (200, 80, 20)],
    "plasma": [(230, 252, 255), (130, 230, 255), (60, 140, 255), (20, 60, 200)],
    "bfg": [(235, 255, 235), (140, 255, 160), (50, 220, 100), (10, 120, 50)],
    "missile": [(255, 250, 210), (255, 200, 80), (240, 110, 30), (90, 50, 30)],
}
SIZES = {"gun_small": 30, "gun_big": 46, "gun_mid": 36, "missile": 44, "plasma": 38, "bfg": 58}


def flash_image(kind, index, count):
    """A procedural muzzle flash: a ragged starburst with a bright core, bigger toward later frames for the rocket."""
    pal = PALETTES["gun" if kind.startswith("gun") else kind]
    size = SIZES[kind]
    if kind == "missile":                       # the rocket's flash grows into a fireball with smoke
        size = int(size * (0.8 + 0.45 * index))
    rnd = random.Random(f"{kind}-{index}")
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = big / 2
    spikes = 9 if kind != "bfg" else 13
    for layer, (col, shrink) in enumerate(zip(pal, (1.0, 0.78, 0.55, 0.32))):
        pts = []
        for i in range(spikes * 2):
            ang = math.pi * i / spikes + rnd.uniform(-0.12, 0.12)
            r = (c * 0.95 if i % 2 == 0 else c * 0.45) * shrink * rnd.uniform(0.82, 1.08)
            pts.append((c + math.cos(ang) * r, c + math.sin(ang) * r))
        d.polygon(pts, fill=col + (255,))
    if kind == "missile" and index >= 2:        # dark smoke rim on the later frames
        d.ellipse((c * 0.25, c * 0.25, c * 1.75, c * 1.75), outline=pal[3] + (255,), width=max(2, size // 6))
    img = img.resize((size, size), Image.NEAREST)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sprites")
    ap.add_argument("--buildcfg")
    args = ap.parse_args()

    pal = dl.load_palette(args.playpal)
    if args.sprites:
        gun_models.TEXTURE_ROOT = args.sprites      # texture the guns with their TGMC icons
    lumps = []
    nw, nh = CANVAS
    muzzle_row = {}
    for prefix in gun_models.MODELS:
        frames = sorted(glob.glob(os.path.join(args.freedoom, prefix.lower() + "[a-z]0.png")))
        if not frames:
            print(f"skip {prefix}: no frames")
            continue
        rest, fit = gun_models.render_weapon(prefix, CANVAS)
        muzzle_row[prefix] = rest.getchannel("A").getbbox()[1]
        left = nw // 2 - (SCREEN_CENTRE_X - 1)          # sprite centred on the screen
        top = nh - (SCREEN_BOTTOM - 32)                  # bottom edge on the bottom of the screen
        for f in frames:
            letter = os.path.basename(f)[4].upper()
            back, up = RECOIL.get(prefix, {}).get(letter, (0, 0))
            img = rest if (back, up) == (0, 0) else gun_models.render_weapon(prefix, CANVAS, back=back, up=up, fit=fit)[0]
            lumps.append((f"{prefix}{letter}0", dl.encode_patch(nw, nh, dl.to_grid(img, pal), left, top)))
        print(f"{prefix}: {len(frames)} frames, muzzle at row {muzzle_row[prefix]}")

    for fprefix, (wprefix, kind) in FLASHES.items():
        files = sorted(glob.glob(os.path.join(args.freedoom, fprefix.lower() + "[a-z]0.png")))
        if not files or wprefix not in muzzle_row:
            continue
        muzzle_y = (SCREEN_BOTTOM - nh) + muzzle_row[wprefix]
        for i, f in enumerate(files):
            letter = os.path.basename(f)[4].upper()
            img = flash_image(kind, i, len(files))
            fw, fh = img.size
            left = fw // 2 - (SCREEN_CENTRE_X - 1)
            top_edge = muzzle_y - int(fh * 0.55)
            top = 32 - top_edge
            lumps.append((f"{fprefix}{letter}0", dl.encode_patch(fw, fh, dl.to_grid(img, pal), left, top)))
        print(f"{fprefix}: {len(files)} flash frames ({kind})")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
