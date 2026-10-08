"""Composite TGMC humanoids per direction: r_human body parts + gear layers, saved as d0..d3 PNGs.

usage: compose_units.py OUTDIR NAME:SHEET:STATE [NAME:SHEET:STATE ...]
  gear layers are applied bottom to top in the order given.
"""
import json
import os
import sys

from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
BODY_ORDER = ["r_leg", "l_leg", "r_foot", "l_foot", "groin_m", "torso_m", "r_arm", "l_arm", "r_hand", "l_hand", "head_m"]


def sheet_index(sheet):
    m = json.load(open(f"{S}/tgmc_sprites/{sheet}/manifest.json"))
    return {s["name"]: s["files"] for s in m["states"]}


CANVAS = (64, 32)  # wide enough for 64px gun art; narrower layers are centred horizontally


def pick(index, state, d, sheet):
    return Image.open(f"{S}/tgmc_sprites/{sheet}/{index[state][d]}").convert("RGBA")


def paste_centered(canvas, layer):
    layer_canvas = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer_canvas.paste(layer, ((canvas.width - layer.width) // 2, 0))
    canvas.alpha_composite(layer_canvas)


def main():
    outdir = sys.argv[1]
    gear = [g.split(":", 2) for g in sys.argv[2:]]
    body = sheet_index("r_human")
    gear_idx = {sh: sheet_index(sh) for _, sh, _ in gear}
    os.makedirs(outdir, exist_ok=True)
    for d in range(4):
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        for name in BODY_ORDER:
            paste_centered(canvas, pick(body, name, d, "r_human"))
        for _, sheet, state in gear:
            paste_centered(canvas, pick(gear_idx[sheet], state, d, sheet))
        canvas.save(f"{outdir}/d{d}.png")
    print("wrote", outdir)


if __name__ == "__main__":
    main()
