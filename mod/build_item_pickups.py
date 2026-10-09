"""Build a PWAD that replaces Freedoom's armor and medical pickups with TGMC item art.

Mapping:
  ARM1 (green armor)   <- obj marine_armor:grenadier     M3 pattern marine armor
  ARM2 (blue armor)    <- obj marine_armor:marine_riot   M5 riot armor (darker, so the two read apart)
  BON2 (armor bonus)   <- obj marine_helmets:helmet      M10 helmet
  STIM (stimpack)      <- syringe:autoinjector-3         bicaridine autoinjector
  MEDI (medikit)       <- stack_objects:brutepack        roll of gauze (bandages)
  BON1 (health bonus)  <- chemistry:pill5                red pill (bicaridine is red in TGMC)

The sheets come from icons/obj/..., whose names clash with the mob sheets (marine_armor, marine_helmets),
so extract them into their own folder and pass it as --sprites. Every Freedoom frame of a pickup is
replaced: armor blinks between A and a brighter B, the bonuses pulse through A-D. Each icon is cropped,
fitted to the Freedoom pickup's size (per-item limits, never more than MAX_UPSCALE), and keeps the
pickup's anchor from buildcfg.txt, scaled with the image.

usage: build_item_pickups.py --sprites DIR --freedoom SPRITES_DIR --buildcfg FILE --playpal IWAD --out WAD
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import anchor_for, load_buildcfg  # noqa: E402

# prefix, sheet, state, width limit and height limit (x the Freedoom pickup's), rotation in degrees
MAPPING = [
    ("ARM1", "marine_armor", "grenadier", 1.1, 1.3, 0),
    ("ARM2", "marine_armor", "marine_riot", 1.1, 1.3, 0),
    ("BON2", "marine_helmets", "helmet", 1.5, 1.2, 0),
    ("STIM", "syringe", "autoinjector-3", 2.0, 2.0, 30),
    ("MEDI", "stack_objects", "brutepack", 1.0, 1.4, 0),
    ("BON1", "chemistry", "pill5", 1.8, 1.0, 0),
]
MAX_UPSCALE = 2.0
# brightness per frame letter: armor blinks, bonuses pulse
GLOW = {"A": 1.0, "B": 1.25, "C": 1.4, "D": 1.2}


def tgmc_icon(root, sheet, state):
    m = json.load(open(os.path.join(root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state]
    if not hit:
        raise KeyError(f"{sheet}:{state}")
    return Image.open(os.path.join(root, sheet, hit[0]["files"][0])).convert("RGBA")


def brighten(img, factor):
    if factor == 1.0:
        return img
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(factor).convert("RGBA")
    rgb.putalpha(img.getchannel("A"))
    return rgb


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
    for prefix, sheet, state, wf, hf, rot in MAPPING:
        frames = sorted(glob.glob(os.path.join(args.freedoom, prefix.lower() + "[a-z]0.png")))
        if not frames:
            print(f"skip {prefix}: no Freedoom frames")
            continue
        orig = Image.open(frames[0])
        (left, top), _ = anchor_for(table, prefix, "A", 0)
        art = tgmc_icon(args.sprites, sheet, state)
        if rot:
            art = art.rotate(rot, resample=Image.NEAREST, expand=True)
        art = dl.crop_content(art)
        fit = min(orig.width * wf / art.width, orig.height * hf / art.height, MAX_UPSCALE)
        nw, nh = max(1, round(art.width * fit)), max(1, round(art.height * fit))
        art = art.resize((nw, nh), Image.NEAREST)
        new_left = round(left * nw / orig.width)
        new_top = round(top * nh / orig.height)
        for f in frames:
            letter = os.path.basename(f)[4].upper()
            img = brighten(art, GLOW.get(letter, 1.0))
            lumps.append((f"{prefix}{letter}0", dl.encode_patch(nw, nh, dl.to_grid(img, pal), new_left, new_top)))
        print(f"{prefix}: {sheet}:{state} -> {nw}x{nh} (orig {orig.width}x{orig.height}), "
              f"{len(frames)} frames, anchor ({new_left},{new_top})")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
