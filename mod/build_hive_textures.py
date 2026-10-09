"""Turn Freedoom's flesh ("hell") wall textures and snake-skin floors into a TGMC xeno hive (GZDoom/UZDoom).

Walls are tiled from TGMC's resin wall tiles (icons/Xeno/structures.dmi, 32x32, the fully connected smoothing
state 15 tiles seamlessly): thick purple resin for the flesh walls, ribbed resin columns for the snake textures,
ribbed resin rows for the spine textures. Weeds creep up from the bottom edge (weeds.dmi weedwall), and the
skull and face textures get xeno eggs and a resin pod set into the resin. Floors (SFLR6/SFLR7) become weeds.
Each texture keeps its Freedoom size, so alignment in the maps does not change. The images are stored as
full-colour PNGs between TX_START and TX_END, which GZDoom uses to replace textures and flats of the same
name. They are not reduced to the Doom palette: it has almost no purples or teals, and the resin turned into
flat navy and grey. GZDoom's hardware renderer shows them as drawn.

usage: build_hive_textures.py --sprites DIR --out WAD
  DIR holds the extracted structures, weeds, Effects and resin_pod sheets (extract_dmi.py output).
"""
import argparse
import io
import json
import os
import random
import struct
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402

# texture name -> (width, height, style); sizes are Freedoom's (the same in freedoom1.wad and freedoom2.wad)
WALLS = {
    "SKIN2": (128, 128, "resin"), "SKINBORD": (64, 128, "resin"), "SKINCUT": (256, 128, "resin"),
    "SKINEDGE": (128, 128, "resin"), "SKINLOW": (256, 104, "resin"), "SKINMET1": (256, 128, "resin"),
    "SKINMET2": (256, 128, "resin"), "SKINSCAB": (256, 128, "resin"), "SKINTEK1": (256, 128, "resin"),
    "SKINTEK2": (256, 128, "resin"), "SLOPPY1": (64, 128, "resin"), "SLOPPY2": (64, 128, "resin"),
    "SK_LEFT": (64, 128, "resin"), "SK_RIGHT": (64, 128, "resin"),
    "SKSNAKE1": (64, 128, "columns"), "SKSNAKE2": (64, 128, "columns"), "SKSNAKE3": (64, 128, "columns"),
    "SKSNAKE4": (64, 128, "columns"),
    "SKSPINE1": (128, 128, "rows"), "SKSPINE2": (256, 96, "rows"),
    "SKULWALL": (128, 128, "eggs"), "SKULWAL3": (128, 128, "eggs"),
    "SKINFACE": (256, 128, "pod"), "SKINSYMB": (256, 128, "pod"),
}
FLATS = ["SFLR6_1", "SFLR6_4", "SFLR7_1", "SFLR7_4"]
TILE = {"resin": "thickresin15", "columns": "resin3", "rows": "resin12", "eggs": "thickresin15",
        "pod": "thickresin15"}
BRIGHTNESS = 1.9   # TGMC's resin is drawn for a lit top-down view; Doom's sector light darkens it further


class Sheets:
    def __init__(self, root):
        self.root = root
        self.cache = {}

    def get(self, sheet, state, frame=0):
        if sheet not in self.cache:
            m = json.load(open(os.path.join(self.root, sheet, "manifest.json")))
            self.cache[sheet] = {s["name"]: s["files"] for s in m["states"]}
        return Image.open(os.path.join(self.root, sheet, self.cache[sheet][state][frame])).convert("RGBA")


def tiled(tile, w, h):
    out = Image.new("RGBA", (w, h))
    for y in range(0, h, tile.height):
        for x in range(0, w, tile.width):
            out.paste(tile, (x, y))
    return out


def wall(sheets, name, w, h, style, rnd):
    img = tiled(sheets.get("structures", TILE[style]), w, h)
    # weeds creeping up from the floor along the bottom edge
    for x in range(0, w, 32):
        weed = sheets.get("weeds", f"weedwall{rnd.choice([0, 1, 4, 5, 8, 12])}")
        img.alpha_composite(weed, (x, h - 32))
    if style == "eggs":
        for x in range(8, w - 24, 44):
            egg = sheets.get("Effects", rnd.choice(["egg_hugger1", "egg_hugger2"]))
            img.alpha_composite(egg, (x, h - 32 - rnd.randint(0, 12)))
            img.alpha_composite(egg, (x + 12, rnd.randint(10, 40)))
    elif style == "pod":
        pod = dl.crop_content(sheets.get("resin_pod", "resinpod"))
        pod = pod.resize((pod.width * 2, pod.height * 2), Image.NEAREST)
        img.alpha_composite(pod, ((w - pod.width) // 2, (h - pod.height) // 2))
    return img


def flat(sheets, rnd):
    img = Image.new("RGBA", (64, 64), (18, 16, 22, 255))
    for y in (0, 32):
        for x in (0, 32):
            img.alpha_composite(sheets.get("weeds", rnd.choice(["weed15", "weed15", "weed0", "weed5", "weed10"])), (x, y))
    return img


def png(img, brightness=BRIGHTNESS):
    """Brighten and return the bytes of an RGB PNG."""
    img = ImageEnhance.Brightness(img.convert("RGB")).enhance(brightness)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sheets = Sheets(args.sprites)
    lumps = [("TX_START", b"")]
    for name, (w, h, style) in WALLS.items():
        lumps.append((name, png(wall(sheets, name, w, h, style, random.Random(name)))))
    for name in FLATS:
        lumps.append((name, png(flat(sheets, random.Random(name)))))
    # a darker weed floor for the story text screens (their BGFLAT, set by build_presentation.py)
    lumps.append(("TGMCSTRY", png(flat(sheets, random.Random("story")), brightness=0.8)))
    lumps.append(("TX_END", b""))
    data, directory, pos = b"", b"", 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    with open(args.out, "wb") as f:
        f.write(struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory)
    print(f"wrote {args.out}: {len(WALLS)} wall textures, {len(FLATS)} flats")


if __name__ == "__main__":
    main()
