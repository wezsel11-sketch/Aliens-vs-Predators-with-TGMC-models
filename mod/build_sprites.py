"""Build a PWAD that replaces one Freedoom actor's frames with four TGMC direction images.

  --prefix PLAY|TROO      Freedoom sprite prefix
  --frames ABCD           frame letters to replace
  --d0..--d3 PNG          TGMC images for S, N, E, W (BYOND 4-dir order assumed)
  --freedoom DIR          freedoom sprites dir (for source sizes)
  --buildcfg FILE         freedoom buildcfg.txt (anchor offsets)
  --playpal FILE
  --out FILE.wad

Rotation mapping (same as the imp build): rot1<-S, rot2<-S, rot3<-E, rot4<-N,
rot5<-N, rot6<-mirror(N), rot7<-W, rot8<-mirror(S).
Each lump's size and anchor are scaled from the Freedoom lump it replaces.
"""
import argparse
import glob
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402

ROT_SOURCE = {1: ("d0", False), 2: ("d0", False), 3: ("d2", False), 4: ("d1", False),
              5: ("d1", False), 6: ("d1", True), 7: ("d3", False), 8: ("d0", True)}


def load_buildcfg(path):
    """Map lump-name -> (left, top) from Freedoom buildcfg. Keys may cover several rotations (e.g. PLAYA2A8)."""
    table = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            parts = raw.split(";")[0].split()  # drop trailing comments
            if len(parts) >= 3 and parts[1].lstrip("-").isdigit() and parts[2].lstrip("-").isdigit():
                table[parts[0].upper()] = (int(parts[1]), int(parts[2]))
    return table


def rotations_in(suffix):
    """Rotation numbers named in a suffix such as '' (rot 1 only), '5', or '2A8' (rots 2 and 8)."""
    return {int(c) for c in suffix if c.isdigit()}


def anchor_for(table, prefix, frame, rot):
    """Freedoom anchor for lump PREFIX+frame+rot, which may be listed under a combined key like TROOA2A8."""
    for key, val in table.items():
        if not key.startswith(prefix + frame):
            continue
        suffix = key[len(prefix) + len(frame):]
        if rot in rotations_in(suffix):
            return val, key
    raise KeyError(f"no buildcfg anchor for {prefix}{frame}{rot}")


def source_png_for(freedoom_dir, prefix, frame, rot):
    """The Freedoom PNG holding rotation `rot` for this frame (combined files like playa2a8.png)."""
    base = f"{prefix}{frame}".lower()
    for path in glob.glob(os.path.join(freedoom_dir, base + "*.png")):
        stem = os.path.splitext(os.path.basename(path))[0]
        suffix = stem[len(base):]
        if (suffix == "" and rot == 1) or rot in rotations_in(suffix):
            return path
    raise KeyError(f"no Freedoom png for {prefix}{frame}{rot}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--d0", required=True)
    ap.add_argument("--d1", required=True)
    ap.add_argument("--d2", required=True)
    ap.add_argument("--d3", required=True)
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--buildcfg", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--attack-frames", default="", help="frames that use the same 4 directions (static attack pose)")
    ap.add_argument("--death-frames", default="", help="single-rotation frames (lumps X0) that use --death-png")
    ap.add_argument("--death-png", default="", help="image for the death frames (constant scale, same as the living sprite)")
    ap.add_argument("--death-tilt-src", default="", help="standing image to tip over across the death frames (humans)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pal = dl.load_palette(args.playpal)
    table = load_buildcfg(args.buildcfg)
    dirs = {f"d{i}": dl.crop_content(Image.open(p)) for i, p in enumerate([args.d0, args.d1, args.d2, args.d3])}

    lumps = []
    for frame in args.frames + args.attack_frames:
        for rot in range(1, 9):
            key, mirror = ROT_SOURCE[rot]
            art = dirs[key]
            if mirror:
                art = art.transpose(Image.FLIP_LEFT_RIGHT)
            lumps.append(make_lump(args, table, pal, frame, rot, art))
    if args.death_frames:
        if not (args.death_png or args.death_tilt_src):
            raise SystemExit("--death-frames needs --death-png or --death-tilt-src")
        # Death frames keep the living sprite's pixel scale (Freedoom's death frames get shorter and
        # shorter, so fitting each one to its original height would shrink the corpse to a speck).
        orig_a1 = Image.open(source_png_for(args.freedoom, args.prefix, args.frames[0], 1))
        living_scale = orig_a1.height / dirs["d0"].height
        n = len(args.death_frames)
        for i, frame in enumerate(args.death_frames):
            if args.death_tilt_src:
                # Tip the standing figure over: about 20 degrees on the first frame, flat on the last.
                angle = 20 + (90 - 20) * i / max(1, n - 1)
                art = dl.crop_content(Image.open(args.death_tilt_src).rotate(-angle, expand=True, resample=Image.NEAREST))
            else:
                art = dl.crop_content(Image.open(args.death_png))
            lumps.append(make_fixed_scale_lump(args, pal, frame, art, living_scale))
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out}: {len(lumps)} lumps ({args.prefix} walk {args.frames}, attack {args.attack_frames or '-'}, death {args.death_frames or '-'})")


def make_lump(args, table, pal, frame, rot, art):
    """Scale one direction image to its Freedoom lump's size and anchor, and return (lump name, patch bytes)."""
    src_png = source_png_for(args.freedoom, args.prefix, frame, rot)
    orig = Image.open(src_png).convert("RGBA")
    (left, top), _ = anchor_for(table, args.prefix, frame, rot)
    # Scale to the original lump's height, keeping aspect; anchor scaled proportionally.
    scale = orig.height / art.height
    nw, nh = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((nw, nh), Image.NEAREST)
    new_left = round(left * nw / orig.width)
    new_top = round(top * nh / orig.height)
    return (f"{args.prefix}{frame}{rot}", dl.encode_patch(nw, nh, dl.to_grid(art, pal), new_left, new_top))


def make_fixed_scale_lump(args, pal, frame, art, scale):
    """Scale `art` by a fixed factor and anchor it at the bottom centre (feet on the floor)."""
    nw, nh = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((nw, nh), Image.NEAREST)
    return (f"{args.prefix}{frame}0", dl.encode_patch(nw, nh, dl.to_grid(art, pal), nw // 2, nh))


if __name__ == "__main__":
    main()
