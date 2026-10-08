"""Merge several PWADs into one, keeping lump order. Sprite marker pairs are collapsed into one block.

usage: merge_wads.py OUT.wad IN1.wad IN2.wad ...
"""
import struct
import sys


def read(path):
    d = open(path, "rb").read()
    _, n, o = struct.unpack("<4sII", d[:12])
    out = []
    for i in range(n):
        p, s, nm = struct.unpack("<II8s", d[o + 16 * i:o + 16 * i + 16])
        out.append((nm.rstrip(b"\0").decode("ascii"), d[p:p + s]))
    return out


def main():
    out_path, ins = sys.argv[1], sys.argv[2:]
    sprites, others = [], []
    for path in ins:
        for name, body in read(path):
            if name in ("S_START", "S_END"):
                continue
            # sprite patches have a 4-letter prefix + frame/rotation; everything else (DECORATE, DS*...) goes outside
            (others if name.startswith("DS") or name in ("DECORATE", "DEHACKED", "ZSCRIPT", "MAPINFO", "ANIMDEFS", "SNDINFO") else sprites).append((name, body))
    entries = [("S_START", b"")] + sprites + [("S_END", b"")] + others
    data, directory, pos = b"", b"", 12
    for name, body in entries:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    open(out_path, "wb").write(struct.pack("<4sII", b"PWAD", len(entries), 12 + len(data)) + data + directory)
    print(f"wrote {out_path}: {len(sprites)} sprite lumps, {len(others)} other lumps")


if __name__ == "__main__":
    main()
