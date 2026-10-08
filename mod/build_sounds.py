"""Build a PWAD of Doom sound lumps (DS*) from TGMC OGG files.

Doom's DMX sound lump: u16 format (3), u16 rate (11025), u32 sample count, then
8-bit unsigned mono PCM with 16 bytes of padding each side (count includes padding).

  --map NAME=ogg_path [NAME=ogg_path ...]   e.g. DSPISTOL=.../pistol.ogg
  --raw NAME=file [NAME=file ...]            add raw lumps, e.g. DEHACKED=sound_slots.deh
  --max-seconds N                            trim long tails (default 2.0)
  --out FILE.wad
"""
import argparse
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402

RATE = 11025
PAD = 16


def ogg_to_u8(path, max_seconds):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-t", str(max_seconds),
           "-ac", "1", "-ar", str(RATE), "-f", "u8", "-acodec", "pcm_u8", "-"]
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def ds_lump(samples):
    pad = bytes([0x80]) * PAD
    body = pad + samples + pad
    return struct.pack("<HHI", 3, RATE, len(body)) + body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", nargs="+", required=True)
    ap.add_argument("--raw", nargs="*", default=[], help="NAME=file: add a file as a raw lump (e.g. DEHACKED)")
    ap.add_argument("--max-seconds", type=float, default=2.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    lumps = []
    for item in args.map:
        name, path = item.split("=", 1)
        samples = ogg_to_u8(path, args.max_seconds)
        lumps.append((name.upper(), ds_lump(samples)))
        print(f"{name.upper()}: {len(samples)} samples (~{len(samples) / RATE:.2f}s) from {os.path.basename(path)}")
    for item in args.raw:
        name, path = item.split("=", 1)
        with open(path, "rb") as f:
            lumps.append((name.upper(), f.read()))
        print(f"{name.upper()}: raw lump from {os.path.basename(path)}")
    # build_wad wraps in S_START/S_END, which is for sprites; sounds need no markers.
    entries = lumps
    data, directory, pos = b"", b"", 12
    for name, body in entries:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    header = struct.pack("<4sII", b"PWAD", len(entries), 12 + len(data))
    with open(args.out, "wb") as f:
        f.write(header + data + directory)
    print(f"wrote {args.out} with {len(entries)} sound lumps")


if __name__ == "__main__":
    main()
