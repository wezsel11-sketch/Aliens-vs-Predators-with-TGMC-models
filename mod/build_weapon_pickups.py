"""Build a PWAD that replaces Freedoom's weapon pickups with TGMC gun art.

Mapping (by gun class):
  SHOTA0 <- shotguns64:trenchgun     SGN2A0 <- shotguns:dshotgun
  MGUNA0 <- machineguns64:t60        LAUNA0 <- special64:rpg
  PLASA0 <- plasma64:plasma_rifle    BFUGA0 <- plasma64:plasma_cannon
  CSAWA0 <- twohanded:auto_axe_on    (no chainsaw art in TGMC; the powered axe is closest)

Each icon is cropped to content, fitted to the Freedoom pickup's size (width-limited, height
capped), and keeps the pickup's anchor from buildcfg.txt, scaled with the image.

usage: build_weapon_pickups.py --sprites DIR --freedoom SPRITES_DIR --buildcfg FILE --playpal IWAD --out WAD
"""
import argparse
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import anchor_for, load_buildcfg  # noqa: E402

MAPPING = [
    ("SHOT", "shotguns64", "trenchgun"),
    ("SGN2", "shotguns", "dshotgun"),
    ("MGUN", "machineguns64", "t60"),
    ("LAUN", "special64", "rpg"),
    ("PLAS", "plasma64", "plasma_rifle"),
    ("BFUG", "plasma64", "plasma_cannon"),
    ("CSAW", "twohanded", "auto_axe_on"),
]
MAX_HEIGHT_FACTOR = 1.4  # allow a bit taller than the original pickup, never wider


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
        orig_path = os.path.join(args.freedoom, f"{prefix.lower()}a0.png")
        if not os.path.exists(orig_path):
            print(f"skip {prefix}: no Freedoom sprite {os.path.basename(orig_path)}")
            continue
        orig = Image.open(orig_path)
        (left, top), _ = anchor_for(table, prefix, "A", 0)
        art = dl.crop_content(tgmc_icon(args.sprites, sheet, state))
        fit = min(orig.width / art.width, orig.height * MAX_HEIGHT_FACTOR / art.height)
        nw, nh = max(1, round(art.width * fit)), max(1, round(art.height * fit))
        art = art.resize((nw, nh), Image.NEAREST)
        new_left = round(left * nw / orig.width)
        new_top = round(top * nh / orig.height)
        lumps.append((f"{prefix}A0", dl.encode_patch(nw, nh, dl.to_grid(art, pal), new_left, new_top)))
        print(f"{prefix}A0: {sheet}:{state} -> {nw}x{nh} (orig {orig.width}x{orig.height}), anchor ({new_left},{new_top})")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
