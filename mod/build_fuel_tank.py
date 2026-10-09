"""Replace Freedoom's explosive barrel with the SS13/TGMC fuel tank and its explosion with TGMC's.

  BAR1A0, BAR1B0 (standing barrel)     <- objects:weldtank (the red fuel tank)
  BEXPA0, BEXPB0 (barrel about to blow) <- the fuel tank, then the fuel tank glowing hot
  BEXPC0..BEXPE0 (the blast)            <- icons/effects/96x96.dmi "explosion" frames (fireball to smoke)
The tank keeps the barrel's height and anchor (buildcfg.txt); the blast is centred on the tank.

usage: build_fuel_tank.py --sprites DIR --buildcfg FILE --freedoom SPRITES_DIR --playpal IWAD --out WAD
  DIR holds the extracted objects and 96x96 sheets.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import anchor_for, load_buildcfg  # noqa: E402

TANK_HEIGHT = 1.15       # x the Freedoom barrel's height
BLAST_FRAMES = {"C": (6, 56), "D": (12, 76), "E": (22, 84)}   # letter -> (explosion frame, size in pixels)


def frames(root, sheet, state):
    m = json.load(open(os.path.join(root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state][0]
    return [Image.open(os.path.join(root, sheet, f)).convert("RGBA") for f in hit["files"]]


def solid(img):
    """Doom patches have no partial transparency: keep pixels that are mostly opaque."""
    img = img.copy()
    img.putalpha(img.getchannel("A").point(lambda v: 255 if v > 110 else 0))
    return img


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

    barrel = Image.open(os.path.join(args.freedoom, "bar1a0.png"))
    (left, top), _ = anchor_for(table, "BAR1", "A", 0)
    tank = dl.crop_content(frames(args.sprites, "objects", "weldtank")[0])
    scale = barrel.height * TANK_HEIGHT / tank.height
    tank = tank.resize((round(tank.width * scale), round(tank.height * scale)), Image.NEAREST)
    # anchor: the barrel's own anchor scaled to the tank (feet on the floor, centred)
    t_left, t_top = round(left * tank.width / barrel.width), round(top * tank.height / barrel.height)
    hot = ImageEnhance.Brightness(tank.convert("RGB")).enhance(1.5).convert("RGBA")
    hot.putalpha(tank.getchannel("A"))

    lumps = []
    for name, img in [("BAR1A0", tank), ("BAR1B0", tank), ("BEXPA0", tank), ("BEXPB0", hot)]:
        lumps.append((name, dl.encode_patch(img.width, img.height, dl.to_grid(img, pal), t_left, t_top)))
    boom = frames(args.sprites, "96x96", "explosion")
    for letter, (index, size) in BLAST_FRAMES.items():
        img = solid(dl.crop_content(boom[index]).resize((size, size), Image.LANCZOS))
        # centre the blast on the middle of the tank
        lumps.append((f"BEXP{letter}0", dl.encode_patch(size, size, dl.to_grid(img, pal),
                                                         size // 2, size // 2 + t_top // 2)))
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out}: fuel tank {tank.size}, blast frames {list(BLAST_FRAMES)}")


if __name__ == "__main__":
    main()
