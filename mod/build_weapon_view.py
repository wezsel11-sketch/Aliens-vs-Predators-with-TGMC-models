"""Replace Freedoom's first-person weapon sprites with voxel guns built from TGMC side-view art.

TGMC has only side-view gun art, so voxel_gun.py extrudes each icon into a small 3D voxel model and
renders it from a camera behind, above and to the right, with two forearms. The render has the
same height as the Freedoom sprite it replaces. It is mirrored and tipped toward the middle of the
screen so the gun sits at the bottom right with the muzzle pointing in. Every frame of a weapon gets the same
image (no recoil animation). Muzzle flash sprites (PISF, SHTF, ...) stay Freedoom's.

usage: build_weapon_view.py --sprites DIR --freedoom SPRITES_DIR --buildcfg FILE --playpal IWAD --out WAD
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
import voxel_gun  # noqa: E402
from build_sprites import anchor_for, load_buildcfg  # noqa: E402

SHIFT_X = 0    # pixels to the right of the original sprite centre (0 = classic Doom, centred)
TILT = 18      # degrees the gun is tipped toward the middle of the screen

MAPPING = [
    ("PISG", "pistols", "m1911"),
    ("SHTG", "shotguns64", "trenchgun"),
    ("SHT2", "shotguns", "dshotgun"),
    ("CHGG", "machineguns64", "t60"),
    ("MISG", "special64", "rpg"),
    ("PLSG", "plasma64", "plasma_rifle"),
    ("BFGG", "plasma64", "plasma_cannon"),
    ("SAWG", "twohanded", "auto_axe_on"),
]


def tgmc_icon(root, sheet, state):
    m = json.load(open(os.path.join(root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state]
    if not hit:
        raise KeyError(f"{sheet}:{state}")
    return Image.open(os.path.join(root, sheet, hit[0]["files"][0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", required=True)
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--buildcfg", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pal = dl.load_palette(args.playpal)
    table = load_buildcfg(args.buildcfg)
    lumps = []
    for prefix, sheet, state in MAPPING:
        frames = sorted(glob.glob(os.path.join(args.freedoom, f"{prefix.lower()}[a-z]0.png")))
        if not frames:
            print(f"skip {prefix}: no frames")
            continue
        first = Image.open(frames[0])
        (left, top), _ = anchor_for(table, prefix, "A", 0)
        # Original bottom-centre, measured from the sprite origin (anchor), then moved to the right.
        bx, by = first.width / 2 - left + SHIFT_X, first.height - top
        art = voxel_gun.render(tgmc_icon(args.sprites, sheet, state), size=(first.width * 2, first.height * 2))
        art = voxel_gun.pose_bottom_right(art, TILT)
        scale = first.height / art.height
        nw, nh = max(1, round(art.width * scale)), max(1, round(art.height * scale))
        art = art.resize((nw, nh), Image.NEAREST)
        new_left, new_top = round(nw / 2 - bx), round(nh - by)
        body = dl.encode_patch(nw, nh, dl.to_grid(art, pal), new_left, new_top)
        for f in frames:
            letter = os.path.basename(f)[4].upper()
            lumps.append((f"{prefix}{letter}0", body))
        print(f"{prefix}: {sheet}:{state} -> {nw}x{nh} (orig {first.width}x{first.height}), anchor ({new_left},{new_top}), {len(frames)} frames")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
