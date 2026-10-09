"""Read BYOND map files (.dmm), in both the classic layout and TGM (one block per column).

  keys, grid = load(path)
    keys: {key: [path strings]} - the turf, area and objects on a tile, var edits stripped ("/obj/x{dir = 4}" -> "/obj/x")
    grid: grid[row][col] = key, row 0 at the top (north), as the map is drawn in the editor
"""
import re

_BLOCK = re.compile(r'^\((\d+),(\d+),(\d+)\) = \{"\n(.*?)\n"\}', re.S | re.M)


def _split_paths(body):
    """Split a key's contents '/a,/b{x = "1,2"},/c' into paths, ignoring commas inside {} and quotes."""
    paths, cur, depth, quote = [], [], 0, False
    for ch in body:
        if quote:
            cur.append(ch)
            if ch == '"':
                quote = False
            continue
        if ch == '"':
            quote = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            paths.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    paths.append("".join(cur))
    return [p.strip().split("{")[0].strip() for p in paths if p.strip()]


def _parse_keys(text):
    keys = {}
    i = 0
    pattern = re.compile(r'^"(\w+)" = \(', re.M)
    while True:
        m = pattern.search(text, i)
        if not m:
            break
        j, depth, quote = m.end(), 0, False
        while True:   # find the ')' that closes this key, outside braces and strings
            ch = text[j]
            if quote:
                quote = ch != '"'
            elif ch == '"':
                quote = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == ")" and depth == 0:
                break
            j += 1
        keys[m.group(1)] = _split_paths(text[m.end():j])
        i = j
    return keys


def load(path):
    text = open(path, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    keys = _parse_keys(text)
    blocks = [(int(m.group(1)), int(m.group(2)), m.group(4).split("\n")) for m in _BLOCK.finditer(text)]
    keylen = len(next(iter(keys)))
    if len(blocks) == 1:            # classic: one block, one line per row, keys run together
        x0, y0, rows = blocks[0]
        return keys, [[row[i:i + keylen] for i in range(0, len(row), keylen)] for row in rows]
    # TGM: one block per column x, its lines from the top row down
    height = max(len(lines) for _, _, lines in blocks)
    width = max(x for x, _, _ in blocks)
    grid = [[None] * width for _ in range(height)]
    for x, _, lines in blocks:
        for r, key in enumerate(lines):
            grid[r][x - 1] = key
    return keys, grid
