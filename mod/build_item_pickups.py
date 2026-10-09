"""Build a PWAD that replaces Freedoom's armor, medical, powerup, key and ammo-box pickups, and some
decorations, with TGMC item art.

Mapping:
  ARM1 (green armor)   <- obj marine_armor:grenadier     M3 pattern marine armor
  ARM2 (blue armor)    <- obj marine_armor:marine_riot   M5 riot armor (darker, so the two read apart)
  BON2 (armor bonus)   <- obj marine_helmets:helmet      M10 helmet
  STIM (stimpack)      <- syringe:autoinjector-3         bicaridine autoinjector
  MEDI (medikit)       <- stack_objects:brutepack        roll of gauze (bandages)
  BON1 (health bonus)  <- chemistry:pill5                red pill (bicaridine is red in TGMC)
  PSTR berserk = firstaid:bezerk, SOUL = advfirstaid, MEGA = o2firstaid, BPAK = marine backpack,
  PVIS light amp = night-vision goggles, PMAP map = tablet, SUIT = radiation suit,
  PINV invulnerability = bomb suit, PINS invisibility = xeno costume,
  keys (cards and skulls) = the silver ID card tinted blue, red or yellow (the colours must read at a distance),
  SBOX = buckshot box, BROK = quad rockets, CELL = plasma cell, CELP = powerpack.
  Decorations POL1-POL6 (impaled bodies, skull piles) become xeno eggs, a resin pod and burst-egg remains.

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

# prefix, sheet, state, width limit and height limit (x the Freedoom sprite's), rotation in degrees,
# and optionally {frame letter: state} for sprites whose frames show different pictures (no glow then).
# A state "name#3" means frame 3 of an animated state.
MAPPING = [
    ("ARM1", "marine_armor", "grenadier", 1.1, 1.3, 0),
    ("ARM2", "marine_armor", "marine_riot", 1.1, 1.3, 0),
    ("BON2", "marine_helmets", "helmet", 1.5, 1.2, 0),
    ("STIM", "syringe", "autoinjector-3", 2.0, 2.0, 30),
    ("MEDI", "stack_objects", "brutepack", 1.0, 1.4, 0),
    ("BON1", "chemistry", "pill5", 1.8, 1.0, 0),
    ("PSTR", "firstaid", "bezerk", 1.0, 1.5, 0),
    ("SOUL", "firstaid", "advfirstaid", 1.3, 1.3, 0),
    ("MEGA", "firstaid", "o2firstaid", 1.3, 1.3, 0),
    ("BPAK", "backpack", "marinepack", 1.2, 1.2, 0),
    ("PVIS", "glasses", "night", 1.3, 1.6, 0),
    ("PMAP", "pda", "pda_large_green", 1.0, 1.0, 0),
    ("SUIT", "suits", "rad", 1.4, 1.0, 0),
    ("PINV", "suits", "bomb", 1.6, 1.8, 0),
    ("PINS", "suits", "xenos", 1.5, 1.6, 0),
    ("BKEY", "card", "silver", 1.6, 1.2, 0),
    ("RKEY", "card", "silver", 1.6, 1.2, 0),
    ("YKEY", "card", "silver", 1.6, 1.2, 0),
    ("BSKU", "card", "silver", 1.6, 1.3, 0),
    ("RSKU", "card", "silver", 1.6, 1.3, 0),
    ("YSKU", "card", "silver", 1.6, 1.3, 0),
    ("SBOX", "box", "buckshot", 1.0, 2.0, 0),
    ("BROK", "rocket", "quad_rocket", 1.0, 1.4, 0),
    ("CELL", "energy", "plasma", 1.2, 2.0, 0),
    ("CELP", "powerpack", "powerpack", 1.0, 1.6, 0),
    ("POL1", "resin_pod", "resinpod", 1.6, 0.7, 0),
    ("POL2", "Effects", "egg opening#9", 1.6, 0.55, 0),
    ("POL3", "Effects", "egg_hugger3", 1.6, 0.75, 0),
    ("POL4", "Effects", "egg_hugger2", 1.6, 0.6, 0),
    ("POL5", "Effects", "egg exploding#6", 1.0, 2.5, 0),
    ("POL6", "Effects", "egg_hugger1", 1.6, 0.5, 0, {"A": "egg_hugger1", "B": "egg opening#1"}),
]
MAX_UPSCALE = 2.0
# brightness per frame letter: armor blinks, bonuses pulse
GLOW = {"A": 1.0, "B": 1.25, "C": 1.4, "D": 1.2, "E": 1.1, "F": 1.05}
NO_GLOW = ("POL",)  # decorations do not pulse
_BLUE, _RED, _YELLOW = (80, 130, 255), (255, 70, 60), (255, 220, 70)
TINT = {"BKEY": _BLUE, "BSKU": _BLUE, "RKEY": _RED, "RSKU": _RED, "YKEY": _YELLOW, "YSKU": _YELLOW}


def tgmc_icon(root, sheet, state):
    state, _, index = state.partition("#")
    m = json.load(open(os.path.join(root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state]
    if not hit:
        raise KeyError(f"{sheet}:{state}")
    return Image.open(os.path.join(root, sheet, hit[0]["files"][int(index or 0)])).convert("RGBA")


def tint(img, rgb):
    """Recolour a grey image: each pixel's lightness times the tint colour (alpha kept)."""
    grey = img.convert("L")
    out = Image.merge("RGB", [grey.point(lambda v, c=c: min(255, round(v * c / 160))) for c in rgb]).convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


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
    for prefix, sheet, state, wf, hf, rot, *per_frame in MAPPING:
        per_frame = per_frame[0] if per_frame else {}
        frames = sorted(glob.glob(os.path.join(args.freedoom, prefix.lower() + "[a-z]0.png")))
        if not frames:
            print(f"skip {prefix}: no Freedoom frames")
            continue
        orig = Image.open(frames[0])
        (left, top), _ = anchor_for(table, prefix, "A", 0)

        def load(st):
            art = tgmc_icon(args.sprites, sheet, st)
            if rot:
                art = art.rotate(rot, resample=Image.NEAREST, expand=True)
            if prefix in TINT:
                art = tint(art, TINT[prefix])
            return dl.crop_content(art)

        base = load(state)
        fit = min(orig.width * wf / base.width, orig.height * hf / base.height, MAX_UPSCALE)
        for f in frames:
            letter = os.path.basename(f)[4].upper()
            art = load(per_frame[letter]) if letter in per_frame else base
            nw, nh = max(1, round(art.width * fit)), max(1, round(art.height * fit))
            art = art.resize((nw, nh), Image.NEAREST)
            if not per_frame and not prefix.startswith(NO_GLOW):
                art = brighten(art, GLOW.get(letter, 1.0))
            new_left, new_top = round(left * nw / orig.width), round(top * nh / orig.height)
            lumps.append((f"{prefix}{letter}0", dl.encode_patch(nw, nh, dl.to_grid(art, pal), new_left, new_top)))
        print(f"{prefix}: {sheet}:{state} -> {round(base.width * fit)}x{round(base.height * fit)} "
              f"(orig {orig.width}x{orig.height}), {len(frames)} frames")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
