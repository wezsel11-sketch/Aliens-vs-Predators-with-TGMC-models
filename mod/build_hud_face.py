"""Replace the status bar face with a TGMC marine: a head-and-shoulders crop of the composited marine (helmet,
armor), the same figure as the player sprite (marine_dirs from compose_units.py), scaled up 2x.

Doom's faces: STFST<pain><look> (looking left/ahead/right), STFTL/STFTR<pain>0 (turned left/right), STFOUCH,
STFEVL (grin on a weapon pickup) and STFKILL (rampage) per pain level 0-4, STFGOD0 and STFDEAD0. The marine head
is the front view for the straight faces (shifted a pixel for the glance left/right) and the side views for
the turns; each pain level adds more blood and darker shading, OUCH flashes red, EVL lights the visor, KILL
tints the face red, god mode gilds the helmet, and the dead face is grey, bloodied and tipped over. Sizes and
offsets follow Freedoom's faces (buildcfg.txt).

usage: build_hud_face.py --marine-dirs DIR --freedoom FREEDOOM_ROOT --playpal IWAD --out WAD
  DIR holds d0.png..d3.png (S, N, E, W) from compose_units.py.
"""
import argparse
import os
import random
import struct
import sys

from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import load_buildcfg  # noqa: E402

BUST = 13                 # TGMC pixels: the bust is at most this wide and this tall
SCALE = 2                 # 13 x 2 = 26, about Freedoom's 24x29 faces
BLOOD = [(150, 10, 10), (110, 0, 0), (190, 30, 20)]


def bust(marine_dirs, d):
    """Head and shoulders of the composited marine for direction d (0 S, 1 N, 2 E, 3 W)."""
    img = dl.crop_content(Image.open(os.path.join(marine_dirs, f"d{d}.png")).convert("RGBA"))
    cut = max(0, (img.width - BUST) // 2)
    return dl.crop_content(img.crop((cut, 0, min(img.width, cut + BUST), BUST)))


def scaled(img):
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


def bloodied(img, level, seed):
    """Darken a little and splash blood over the opaque pixels, more for each pain level."""
    alpha = img.getchannel("A")
    img = ImageEnhance.Brightness(img.convert("RGB")).enhance(1.0 - 0.06 * level).convert("RGBA")
    img.putalpha(alpha)
    rnd = random.Random(seed)
    px = img.load()
    solid = [(x, y) for y in range(img.height) for x in range(img.width) if px[x, y][3] > 0]
    for _ in range(level * 2):
        x, y = rnd.choice(solid)
        px[x, y] = rnd.choice(BLOOD) + (255,)
    return img


def tint(img, rgb, amount):
    base = img.convert("RGB")
    out = Image.blend(base, Image.new("RGB", img.size, rgb), amount).convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


def shift(img, dx):
    """The same face moved dx pixels sideways inside its own width (a glance left or right)."""
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(img.crop((max(0, -dx), 0, img.width - max(0, dx), img.height)), (max(0, dx), 0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--marine-dirs", required=True)
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pal = dl.load_palette(args.playpal)
    table = load_buildcfg(os.path.join(args.freedoom, "buildcfg.txt"))
    # everything is drawn at TGMC's native size and scaled up at the end, so blood is in whole TGMC pixels
    front, east, west = bust(args.marine_dirs, 0), bust(args.marine_dirs, 2), bust(args.marine_dirs, 3)
    faces = {}
    for pain in range(5):
        hurt = lambda img, tag: bloodied(img, pain, f"{tag}{pain}")  # noqa: E731
        faces[f"STFST{pain}0"] = shift(hurt(front, "st"), -1)
        faces[f"STFST{pain}1"] = shift(hurt(front, "st"), 0)
        faces[f"STFST{pain}2"] = shift(hurt(front, "st"), 1)
        faces[f"STFTL{pain}0"] = hurt(west, "tl")
        faces[f"STFTR{pain}0"] = hurt(east, "tr")
        faces[f"STFOUCH{pain}"] = tint(hurt(front, "st"), (255, 40, 30), 0.45)
        faces[f"STFEVL{pain}"] = tint(hurt(front, "st"), (255, 255, 220), 0.25)
        faces[f"STFKILL{pain}"] = tint(hurt(front, "st"), (200, 0, 0), 0.25)
    faces["STFGOD0"] = tint(front, (255, 200, 40), 0.4)
    dead = tint(bloodied(front, 6, "dead"), (90, 90, 90), 0.5)
    faces["STFDEAD0"] = dl.crop_content(dead.rotate(-25, expand=True, resample=Image.NEAREST))
    faces = {name: scaled(img) for name, img in faces.items()}
    lumps = []
    for name, img in faces.items():
        left, top = table.get(name, (-5, -2))
        # centre our (narrower) head where Freedoom's 24-pixel-wide face sits
        left += (img.width - 24) // 2
        lumps.append((name, dl.encode_patch(img.width, img.height, dl.to_grid(img, pal), left, top)))
    # status bar graphics live outside the sprite markers
    data, directory, pos = b"", b"", 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    with open(args.out, "wb") as f:
        f.write(struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory)
    print(f"wrote {args.out}: {len(lumps)} faces, {faces['STFST01'].size}")


if __name__ == "__main__":
    main()
