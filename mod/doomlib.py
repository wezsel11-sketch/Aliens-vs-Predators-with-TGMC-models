"""Shared helpers for building Doom sprite PWADs from TGMC art.

Palette, nearest-colour quantizing, Doom patch encoding, PWAD writing,
and reading the grAb offset chunk from Freedoom PNG sprites.
"""
import struct
import zlib

from PIL import Image


def load_palette(path):
    with open(path, "rb") as f:
        data = f.read(768)
    return [tuple(data[i:i + 3]) for i in range(0, 768, 3)]


def read_grab(png_path):
    """Return (leftoffset, topoffset) from a PNG's grAb chunk, or (0, 0) if absent."""
    with open(png_path, "rb") as f:
        data = f.read()
    i = 8
    while i < len(data):
        (n,) = struct.unpack(">I", data[i:i + 4])
        kind = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + n]
        if kind == b"grAb" and n == 8:
            return struct.unpack(">ii", body)
        i += 12 + n
    return (0, 0)


def nearest_index(rgb, pal):
    r, g, b = rgb
    best, best_d = 0, 1 << 30
    for i, (pr, pg, pb) in enumerate(pal):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best, best_d = i, d
    return best


def to_grid(img, pal):
    """RGBA image -> 2D grid of palette indices (None = transparent)."""
    w, h = img.size
    px = img.load()
    grid = [[None] * w for _ in range(h)]
    cache = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            key = (r, g, b)
            if key not in cache:
                cache[key] = nearest_index(key, pal)
            grid[y][x] = cache[key]
    return grid


def encode_patch(w, h, grid, left, top):
    """Doom patch format: header, column offsets, posts per column."""
    columns = []
    for x in range(w):
        col = bytearray()
        y = 0
        while y < h:
            if grid[y][x] is None:
                y += 1
                continue
            start = y
            run = []
            while y < h and grid[y][x] is not None:
                run.append(grid[y][x])
                y += 1
            col += struct.pack("BBB", start, len(run), 0) + bytes(run) + b"\x00"
        col += b"\xff"
        columns.append(bytes(col))
    header_size = 8 + 4 * w
    offsets, body, pos = [], b"", header_size
    for c in columns:
        offsets.append(pos)
        body += c
        pos += len(c)
    header = struct.pack("<hhhh", w, h, left, top)
    header += struct.pack("<%dI" % w, *offsets)
    return header + body


def build_wad(lumps, out_path):
    """lumps: list of (name, bytes). Wraps them in S_START / S_END sprite markers."""
    entries = [("S_START", b"")] + lumps + [("S_END", b"")]
    data = b""
    directory = b""
    pos = 12
    for name, body in entries:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    dir_offset = 12 + len(data)
    header = struct.pack("<4sII", b"PWAD", len(entries), dir_offset)
    with open(out_path, "wb") as f:
        f.write(header + data + directory)


def crop_content(img):
    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty frame")
    return img.crop(bbox)


def decode_patch(b):
    """Decode a Doom patch lump to RGBA (opaque pixels painted a flat colour), for checks."""
    w, h, _, _ = struct.unpack("<hhhh", b[:8])
    offs = struct.unpack("<%dI" % w, b[8:8 + 4 * w])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for x, o in enumerate(offs):
        p = o
        while b[p] != 0xFF:
            top, length = b[p], b[p + 1]
            for k in range(length):
                px[x, top + k] = (180, 140, 90, 255)
            p += 4 + length
    return img
