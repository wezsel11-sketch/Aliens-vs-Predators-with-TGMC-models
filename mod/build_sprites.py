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
import re
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


def frame_rotations(suffix):
    """(frame letter, rotation) pairs named in a lump name suffix.

    'A1' -> [(A,1)]; 'A2A8' -> [(A,2),(A,8)]; 'A1D1' -> [(A,1),(D,1)] (one picture shared by two frames);
    'I0' -> [(I,0)].
    """
    return [(m.group(1).upper(), int(m.group(2))) for m in re.finditer(r"([A-Za-z\[\]\\^])(\d)", suffix)]


def lump_frame(frame):
    """Lump-name spelling of a frame letter: Freedoom's file names write the backslash frame (after Z, [) as ^."""
    return "\\" if frame == "^" else frame


def anchor_for(table, prefix, frame, rot):
    """Freedoom anchor for lump PREFIX+frame+rot, which may be listed under a combined key like TROOA2A8."""
    for key, val in table.items():
        if key.startswith(prefix) and (frame, rot) in frame_rotations(key[len(prefix):]):
            return val, key
    raise KeyError(f"no buildcfg anchor for {prefix}{frame}{rot}")


def source_png_for(freedoom_dir, prefix, frame, rot):
    """The Freedoom PNG holding this frame and rotation (combined files like playa2a8.png, bspia1d1.png)."""
    for path in sorted(glob.glob(os.path.join(freedoom_dir, prefix.lower() + "*.png"))):
        stem = os.path.splitext(os.path.basename(path))[0][len(prefix):]
        if (frame, rot) in frame_rotations(stem):
            return path
    raise KeyError(f"no Freedoom png for {prefix}{frame}{rot}")


def detect_frames(freedoom_dir, prefix):
    """Letters of the prefix's rotating frames (files like xxxxA1, xxxxA2A8) and single-rotation frames (xxxxA0)."""
    rotating, single = set(), set()
    for path in glob.glob(os.path.join(freedoom_dir, prefix.lower() + "*.png")):
        stem = os.path.splitext(os.path.basename(path))[0][len(prefix):]
        # every frame a file names, so shared pictures like skela1d1.png also yield frame D
        for frame, rot in frame_rotations(stem):
            (single if rot == 0 else rotating).add(frame)
    return "".join(sorted(rotating)), "".join(sorted(single))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--frames", default="", help="walk frames, e.g. ABCD (or use --auto-frames)")
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
    ap.add_argument("--auto-frames", action="store_true",
                    help="use every rotating frame of the prefix as walk/attack, every single-rotation frame as death")
    ap.add_argument("--like", default="", help="take frame layout, sizes and anchors from this Freedoom prefix "
                    "(for new sprite names such as a SOM variant of POSS)")
    ap.add_argument("--front-frames", default="",
                    help="single-rotation frames that show the living front view (S), not the corpse: "
                    "attack and pain frames drawn facing the player, like the Archvile's")
    ap.add_argument("--death-tilt-count", type=int, default=0,
                    help="tip the figure over across this many death frames; the rest stay flat (default: all)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="size of the living sprite relative to the Freedoom sprite it replaces (e.g. 0.85)")
    ap.add_argument("--death-scale", type=float, default=0.75,
                    help="size of death frames relative to the living sprite (default 0.75)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    args.ref = args.like or args.prefix  # prefix used to find Freedoom's source sprites
    if args.auto_frames:
        args.frames, args.death_frames = detect_frames(args.freedoom, args.ref)
        args.attack_frames = ""
        args.death_frames = "".join(f for f in args.death_frames if f not in args.front_frames)
    if not args.frames:
        raise SystemExit("need --frames or --auto-frames")

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
        orig_a1 = Image.open(source_png_for(args.freedoom, args.ref, args.frames[0], 1))
        living_scale = orig_a1.height / dirs["d0"].height * args.scale
        n = len(args.death_frames)
        for i, frame in enumerate(args.death_frames):
            if args.death_tilt_src:
                # Tip the standing figure over: about 20 degrees on the first frame, flat on the last.
                tilt_n = args.death_tilt_count or n
                angle = 20 + (90 - 20) * min(i, tilt_n - 1) / max(1, tilt_n - 1)
                art = dl.crop_content(Image.open(args.death_tilt_src).rotate(-angle, expand=True, resample=Image.NEAREST))
            else:
                art = dl.crop_content(Image.open(args.death_png))
            lumps.append(make_fixed_scale_lump(args, pal, frame, art, living_scale * args.death_scale))
    if args.front_frames:
        orig_a1 = Image.open(source_png_for(args.freedoom, args.ref, args.frames[0], 1))
        living_scale = orig_a1.height / dirs["d0"].height * args.scale
        for frame in args.front_frames:
            lumps.append(make_fixed_scale_lump(args, pal, frame, dirs["d0"], living_scale))
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out}: {len(lumps)} lumps ({args.prefix} walk {args.frames}, attack {args.attack_frames or '-'}, death {args.death_frames or '-'}, front {args.front_frames or '-'})")


def make_lump(args, table, pal, frame, rot, art):
    """Scale one direction image to its Freedoom lump's size and anchor, and return (lump name, patch bytes)."""
    src_png = source_png_for(args.freedoom, args.ref, frame, rot)
    orig = Image.open(src_png).convert("RGBA")
    try:
        (left, top), _ = anchor_for(table, args.ref, frame, rot)
    except KeyError:
        left, top = dl.read_grab(src_png)  # offsets stored in the PNG itself
        if (left, top) == (0, 0):
            left, top = orig.width // 2, orig.height  # last resort: bottom centre
    # Scale to the original lump's height, keeping aspect; anchor scaled proportionally.
    scale = orig.height / art.height * args.scale
    nw, nh = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((nw, nh), Image.NEAREST)
    new_left = round(left * nw / orig.width)
    new_top = round(top * nh / orig.height)
    return (f"{args.prefix}{lump_frame(frame)}{rot}", dl.encode_patch(nw, nh, dl.to_grid(art, pal), new_left, new_top))


def make_fixed_scale_lump(args, pal, frame, art, scale):
    """Scale `art` by a fixed factor and anchor it at the bottom centre (feet on the floor)."""
    nw, nh = max(1, round(art.width * scale)), max(1, round(art.height * scale))
    art = art.resize((nw, nh), Image.NEAREST)
    return (f"{args.prefix}{lump_frame(frame)}0", dl.encode_patch(nw, nh, dl.to_grid(art, pal), nw // 2, nh))


if __name__ == "__main__":
    main()
