"""Make a PWAD that replaces E1M1 with a copy that has test monsters placed in front of the player start.

No geometry changes: all map lumps are copied from the IWAD, and only THINGS is edited.
Each THING is 10 bytes: x, y, angle, type, flags (little-endian int16).

usage: build_testmap.py IWAD OUT.wad [--map E1M1] [--distance 160]
"""
import argparse
import math
import struct

MAP_LUMPS = ["THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS", "SSECTORS",
             "NODES", "SECTORS", "REJECT", "BLOCKMAP"]

# Doom thing types for the replaced actors.
TEST_ACTORS = [
    ("POSS zombieman (3004)", 3004),
    ("SPOS shotgun guy (9)", 9),
    ("CPOS chaingunner (65)", 65),
    ("TROO imp (3001)", 3001),
]


def read_directory(data):
    _, numlumps, diroff = struct.unpack("<4sII", data[:12])
    entries = []
    for i in range(numlumps):
        pos, size, name = struct.unpack("<II8s", data[diroff + 16 * i:diroff + 16 * i + 16])
        entries.append((name.rstrip(b"\0").decode("ascii"), pos, size))
    return entries


def lump_bytes(data, entries, name):
    for n, pos, size in entries:
        if n == name:
            return data[pos:pos + size]
    raise KeyError(name)


def build_wad(path, lumps):
    data = b""
    directory = b""
    pos = 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    header = struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data))
    with open(path, "wb") as f:
        f.write(header + data + directory)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iwad")
    ap.add_argument("out")
    ap.add_argument("--map", default="E1M1")
    ap.add_argument("--distance", type=int, default=160)
    args = ap.parse_args()

    data = open(args.iwad, "rb").read()
    entries = read_directory(data)
    things = bytearray(lump_bytes(data, entries, "THINGS"))
    count = len(things) // 10

    # Find the player 1 start: type 1.
    start = None
    for i in range(count):
        x, y, ang, typ, flags = struct.unpack_from("<hhhhh", things, i * 10)
        if typ == 1:
            start = (x, y, ang)
            break
    if start is None:
        raise SystemExit("no player 1 start")
    sx, sy, sang = start
    print(f"player 1 start at ({sx},{sy}) angle {sang}")

    # Place the test actors in a row in front of the player, facing the player.
    fwd = math.radians(sang)
    side = fwd + math.pi / 2
    extra = b""
    for idx, (label, typ) in enumerate(TEST_ACTORS):
        offset = (idx - (len(TEST_ACTORS) - 1) / 2) * 64  # 64 units apart, centred on the view line
        x = int(sx + math.cos(fwd) * args.distance + math.cos(side) * offset)
        y = int(sy + math.sin(fwd) * args.distance + math.sin(side) * offset)
        face = (sang + 180) % 360
        extra += struct.pack("<hhhhh", x, y, face, typ, 7)  # flags 7: easy, normal, hard
        print(f"  {label} at ({x},{y}) facing {face}")

    new_things = bytes(things) + extra
    lumps = [(args.map, b"")]
    for name in MAP_LUMPS:
        body = new_things if name == "THINGS" else lump_bytes(data, entries, name)
        lumps.append((name, body))
    build_wad(args.out, lumps)
    print(f"wrote {args.out} with {len(TEST_ACTORS)} test actors in {args.map}")


if __name__ == "__main__":
    main()
