"""Build a PWAD that recolors existing Freedoom sprites by shifting their hue.

Used to turn the imp's orange fireball (BAL1) into green acid spit. Keeps each sprite's size and
the anchor from buildcfg.txt; colours are re-quantized to the IWAD's PLAYPAL.

usage: build_recolor.py --freedoom SPRITES_DIR --buildcfg FILE --playpal IWAD --out WAD
                        --prefix BAL1 [--shift 90] [--min-sat 0.25]
"""
import argparse
import colorsys
import glob
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import load_buildcfg  # noqa: E402


def shift_hue(img, degrees, min_sat):
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s >= min_sat:  # leave greys and whites alone
                h = (h + degrees / 360.0) % 1.0
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
            px[x, y] = (round(r2 * 255), round(g2 * 255), round(b2 * 255), a)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--buildcfg", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--shift", type=float, default=90.0)
    ap.add_argument("--min-sat", type=float, default=0.25)
    args = ap.parse_args()

    pal = dl.load_palette(args.playpal)
    table = load_buildcfg(args.buildcfg)
    lumps = []
    for path in sorted(glob.glob(os.path.join(args.freedoom, args.prefix.lower() + "*.png"))):
        name = os.path.splitext(os.path.basename(path))[0].upper()
        left, top = table[name]
        art = shift_hue(Image.open(path), args.shift, args.min_sat)
        lumps.append((name, dl.encode_patch(art.width, art.height, dl.to_grid(art, pal), left, top)))
        print(f"{name}: {art.width}x{art.height} anchor ({left},{top})")
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
