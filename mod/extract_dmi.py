"""Extract BYOND .dmi icon files into per-state PNG frames plus a JSON manifest.

A .dmi is a PNG whose zTXt "Description" chunk holds the icon metadata:
icon size, and for each state its dir count and frame count. Icons are packed
state by state, then frame by frame, then direction by direction, laid out
row-major in a grid that is (sheet width / icon width) columns wide.
"""
import json
import os
import re
import struct
import sys
import zlib

from PIL import Image

DIRS_ORDER = [2, 1, 4, 8, 3, 5, 6, 9, 10]  # BYOND direction ids, 1=NORTH etc. (order used by sheet)
DIR_NAMES = {1: "N", 2: "S", 4: "E", 8: "W", 5: "NE", 6: "SE", 9: "NW", 10: "SW"}


def read_description(path):
    with open(path, "rb") as f:
        data = f.read()
    i = 8
    while i < len(data):
        (n,) = struct.unpack(">I", data[i:i + 4])
        kind = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + n]
        if kind == b"zTXt":
            key, _, rest = body.partition(b"\0")
            if key == b"Description":
                return zlib.decompress(rest[1:]).decode("utf-8", errors="replace")
        i += 12 + n
    return None


def parse_meta(text):
    width = height = None
    states = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("width"):
            width = int(line.split("=")[1])
        elif line.startswith("height"):
            height = int(line.split("=")[1])
        elif line.startswith("state"):
            name = re.search(r'"(.*)"', line).group(1)
            cur = {"name": name, "dirs": 1, "frames": 1}
            states.append(cur)
        elif cur is not None and line.startswith("dirs"):
            cur["dirs"] = int(line.split("=")[1])
        elif cur is not None and line.startswith("frames"):
            cur["frames"] = int(line.split("=")[1])
    return width, height, states


def extract(path, out_root):
    text = read_description(path)
    if text is None:
        return {"source": path, "error": "no DMI metadata"}
    sheet = Image.open(path).convert("RGBA")
    icon_w, icon_h = parse_meta(text)[:2]
    _, _, states = parse_meta(text)
    if icon_w is None:
        icon_w = icon_h = 32
    cols = sheet.width // icon_w
    base = os.path.splitext(os.path.basename(path))[0]
    out_dir = os.path.join(out_root, base)
    os.makedirs(out_dir, exist_ok=True)

    index = 0
    manifest = {"source": path, "icon_size": [icon_w, icon_h], "sheet_size": list(sheet.size), "states": []}
    total_expected = sum(s["dirs"] * s["frames"] for s in states)
    for s in states:
        entry = {"name": s["name"], "dirs": s["dirs"], "frames": s["frames"], "files": []}
        for frame in range(s["frames"]):
            for d in range(s["dirs"]):
                x = (index % cols) * icon_w
                y = (index // cols) * icon_h
                crop = sheet.crop((x, y, x + icon_w, y + icon_h))
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", s["name"]) or "state"
                fname = f"{safe}_f{frame}_d{d}.png"
                crop.save(os.path.join(out_dir, fname))
                entry["files"].append(fname)
                index += 1
        manifest["states"].append(entry)
    manifest["icons_expected"] = total_expected
    manifest["icons_extracted"] = index
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    repo, out_root = sys.argv[1], sys.argv[2]
    for rel in sys.argv[3:]:
        m = extract(os.path.join(repo, rel), out_root)
        if "error" in m:
            print("SKIP", rel, m["error"])
            continue
        ok = "OK" if m["icons_expected"] == m["icons_extracted"] else "MISMATCH"
        print(f"{ok} {rel}: states={len(m['states'])} icons={m['icons_extracted']} sheet={m['sheet_size']} icon={m['icon_size']}")
