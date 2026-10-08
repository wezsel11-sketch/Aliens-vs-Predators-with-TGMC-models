"""Build a PWAD that replaces Freedoom's ammo pickups with TGMC magazine and ammo art.

Mapping (chosen from the montage):
  CLIPA0 <- icons/obj/items/ammo/rifle.dmi      state "clip"
  SHELA0 <- icons/mob/inhands/weapons/ammo_left.dmi  state "ammobox_145"
  ROCKA0 <- icons/obj/items/ammo/rocket.dmi     state "shell"
  AMMOA0 <- icons/obj/items/ammo/packet.dmi     state "44_mag"
  CELLA0 is left as Freedoom's.

Each TGMC icon is cropped to its content, scaled up by SCALE, and keeps the
anchor (grAb offsets) of the Freedoom pickup it replaces.
"""
import argparse
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402

SCALE = 1.5
# Freedoom's anchor offsets (left, top) from buildcfg.txt; the PNGs carry no grAb chunk.
FREEDOOM_OFFSETS = {"CLIPA0": (4, 12), "SHELA0": (7, 9), "ROCKA0": (5, 24), "AMMOA0": (8, 16)}
ROTATE = {"ROCKA0": 90}
MAPPING = [
    ("CLIPA0", "rifle", "clip", "clipa0.png"),
    ("SHELA0", "ammo_left", "ammobox_145", "shela0.png"),
    ("ROCKA0", "rocket", "shell", "rocka0.png"),
    ("AMMOA0", "packet", "44_mag", "ammoa0.png"),
]


def tgmc_frame(sprites_root, sheet, state):
    m = json.load(open(os.path.join(sprites_root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state]
    if not hit:
        raise KeyError(f"{sheet}:{state} not in manifest")
    return Image.open(os.path.join(sprites_root, sheet, hit[0]["files"][0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", required=True, help="dir with extracted TGMC sheets (tgmc_sprites)")
    ap.add_argument("--freedoom", required=True, help="freedoom sprites dir")
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pal = dl.load_palette(args.playpal)
    lumps = []
    for lump_name, sheet, state, orig_png in MAPPING:
        orig_path = os.path.join(args.freedoom, orig_png)
        orig = Image.open(orig_path).convert("RGBA")
        left, top = FREEDOOM_OFFSETS[lump_name]
        art = dl.crop_content(tgmc_frame(args.sprites, sheet, state))
        if lump_name in ROTATE:  # TGMC rocket art is horizontal; Doom's pickup is upright
            art = art.rotate(ROTATE[lump_name], expand=True)
        # Fit to 1.5x the original pickup's size, keeping aspect ratio.
        fit = min(orig.width * SCALE / art.width, orig.height * SCALE / art.height)
        nw, nh = max(1, round(art.width * fit)), max(1, round(art.height * fit))
        art = art.resize((nw, nh), Image.NEAREST)
        grid = dl.to_grid(art, pal)
        # Keep the anchor at the same relative point on the new canvas.
        new_left = round(left * nw / orig.width)
        new_top = round(top * nh / orig.height)
        lumps.append((lump_name, dl.encode_patch(nw, nh, grid, new_left, new_top)))
        print(f"{lump_name}: {sheet}:{state} {art.size} from orig {orig.size}, offs ({new_left},{new_top})")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
