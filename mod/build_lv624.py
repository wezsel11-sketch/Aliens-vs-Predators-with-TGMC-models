"""Convert TGMC's LV-624 ground map into a playable GZDoom/UZDoom level (UDMF), as a new episode.

The .dmm map (_maps/map_files/LV624/LV624.dmm, read by dmm.py) is a grid of 32-pixel tiles; each becomes a
64x64 Doom square:
  * closed turfs (walls, rock, dense jungle), framed windows and xeno resin walls are solid; the rest is floor
  * floors get a Freedoom flat after their turf (grass, dirt, sand, plating, tiles, wood, carpet, water); the
    river is sunk 24 units. Outdoor areas (/area/lv624/ground) have the sky above them, the caves a low dark
    rock ceiling, the Lazarus colony buildings a ceiling and indoor light
  * connected tiles of the same kind become one sector, and walls are drawn only where the kind changes, as
    long straight runs (split wherever another wall meets them)
  * airlocks and blast doors become doors that open on use (the landing-zone containment shutters stay open)
  * the area around the xeno silo spawns becomes hive: weed floors and resin walls (hive_textures.wad)
Things: the player starts on landing zone 1, an exit console stands on landing zone 2; xenos spread over the
map's weed nodes (more in the caves), eggs and warriors at the hive, a Praetorian or the Queen at the xeno
start spots, Sons of Mars at some survivor spots, dead marines at the corpse spawners, weapons, ammo and
medical supplies at the supply spawners, fuel tanks where the map has them.
A MAPINFO lump adds the episode "Operation: LV-624" to New Game. GZDoom builds the nodes itself.

usage: build_lv624.py --tgmc TGMC_ROOT --out WAD
"""
import argparse
import collections
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmm  # noqa: E402

MAP = "_maps/map_files/LV624/LV624.dmm"
UNIT = 64

# floor flats by turf (first match wins)
FLOORS = [("water", "FWATER1"), ("dirtgrassborder", "RROCK19"), ("grass", "GRASS1"), ("sand", "RROCK09"),
          ("dirt", "RROCK16"), ("plating", "FLOOR4_8"), ("tile/dark", "CEIL3_5"), ("white", "FLAT20"),
          ("green", "FLOOR7_2"), ("wood", "FLAT5_2"), ("carpet", "FLOOR1_1"), ("ground", "RROCK16")]
DEFAULT_FLOOR = "FLOOR0_3"
# wall textures by solid turf / object
WALLS = [("r_wall", "STARG3"), ("wall/wood", "WOOD1"), ("cult", "MARBLE1"), ("sulaco", "SPACEW2"),
         ("chigusa", "TEKWALL4"), ("/turf/closed/wall", "STARTAN3"), ("gm/dense", "BROVINE2"),
         ("window", "STARGR1"), ("resin", "SKIN2")]
DEFAULT_WALL = "ROCK2"
FACADE = "STARTAN3"            # outside of buildings above the doorways
DOOR_FACE, DOOR_TRACK = "BIGDOOR2", "DOORTRAK"
HIVE_FLOOR, HIVE_WALL, HIVE_RADIUS = "SFLR6_1", "SKIN2", 6
EXIT_TEXTURE = "SW1COMP"

# Doom thing numbers (the mod turns them into TGMC things)
XENOS = [(3002, 30), (3001, 22), (3006, 12), (65, 8), (69, 8), (66, 6), (3005, 4), (3003, 4), (64, 1), (68, 3)]
CAVE_XENOS = [(3002, 25), (3001, 15), (3006, 20), (69, 12), (66, 10), (3003, 6), (64, 1), (65, 8)]
XENO_DENSITY = 0.17       # share of the map's weed nodes that get a xeno
SOM = [3004, 3004, 9]
EGGS = [25, 26, 27, 28, 29]
GUNS = [2001, 2001, 82, 2002, 2002, 2003, 2004, 2005]
AMMO = [2007, 2048, 2008, 2049, 2010, 2046, 2047, 17]
MEDICAL = [2011, 2011, 2012, 2014]


def classify(paths):
    """(kind, turf, area) for one tile: kind is 'solid', 'door' or 'floor'."""
    turf = next((p for p in paths if p.startswith("/turf")), "")
    area = next((p for p in paths if p.startswith("/area")), "")
    objs = [p for p in paths if p.startswith("/obj")]
    if turf.startswith("/turf/closed") or area == "/area/space":
        return "solid", turf, area
    if any(o.startswith(("/obj/structure/window/framed", "/obj/structure/window_frame")) for o in objs):
        return "solid", "window", area
    if "/obj/effect/landmark/xeno_resin_wall" in objs:
        return "solid", "resin", area
    if any(o.startswith("/obj/machinery/door/") and "timed_late" not in o and "door/window" not in o for o in objs):
        return "door", turf, area
    return "floor", turf, area


def pick(table, text, default):
    return next((v for k, v in table if k in text), default)


def zone(area):
    if "caves" in area:
        return "cave"
    if area.startswith("/area/lv624/ground") or area.startswith("/area/shuttle"):
        return "outdoor"
    return "indoor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tgmc", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rnd = random.Random(624)
    keys, grid = dmm.load(os.path.join(args.tgmc, MAP))
    H, W = len(grid), len(grid[0])
    tiles = [[classify(keys[grid[r][c]]) for c in range(W)] for r in range(H)]
    objs = [[[p for p in keys[grid[r][c]] if p.startswith("/obj")] for c in range(W)] for r in range(H)]

    def find(prefix):
        return [(r, c) for r in range(H) for c in range(W) if any(o.startswith(prefix) for o in objs[r][c])]

    silos = find("/obj/effect/landmark/xeno_silo_spawn")
    hive = {(r, c) for r in range(H) for c in range(W)
            if any((r - sr) ** 2 + (c - sc) ** 2 <= HIVE_RADIUS ** 2 for sr, sc in silos)}
    start = find("/obj/docking_port/stationary/marine_dropship/lz1")[0]
    exit_tile = find("/obj/docking_port/stationary/marine_dropship/lz2")[0]

    # ---- sector kind of every open tile
    def tile_key(r, c):
        kind, turf, area = tiles[r][c]
        if kind == "solid":
            return None
        z = zone(area)
        floor = HIVE_FLOOR if (r, c) in hive else pick(FLOORS, turf, DEFAULT_FLOOR)
        fh = -24 if "water" in turf else 0
        if (r, c) == exit_tile:
            return ("exit", "FLOOR4_8", 48, "F_SKY1", 320, 208)
        if kind == "door":
            return ("door", "FLOOR4_8", 0, "FLAT19", 0, 160)
        if z == "outdoor":
            return ("floor", floor, fh, "F_SKY1", 320, 208 if "shuttle" in area else 184)
        if z == "cave":
            return ("floor", floor if (r, c) in hive else ("FLAT10" if "dirt" in turf else floor), fh, "RROCK18", 128,
                    144 if (r, c) in hive else 136)
        return ("floor", floor, fh, "FLAT19", 128, 168)

    tkey = [[tile_key(r, c) for c in range(W)] for r in range(H)]
    sector_of = [[None] * W for _ in range(H)]
    sectors = []
    for r in range(H):
        for c in range(W):
            if tkey[r][c] is None or sector_of[r][c] is not None:
                continue
            sid = len(sectors)
            sectors.append(tkey[r][c])
            todo = [(r, c)]
            sector_of[r][c] = sid
            while todo:
                y, x = todo.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and sector_of[ny][nx] is None and tkey[ny][nx] == tkey[r][c]:
                        sector_of[ny][nx] = sid
                        todo.append((ny, nx))

    def wall_texture(r, c):
        if not (0 <= r < H and 0 <= c < W):
            return DEFAULT_WALL
        if (r, c) in hive and zone(tiles[r][c][2]) == "cave":
            return HIVE_WALL
        return pick(WALLS, tiles[r][c][1], DEFAULT_WALL)

    # ---- the exit must be reachable on foot from the start (through floors and doors)
    seen, todo = {start}, [start]
    while todo:
        y, x = todo.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (y + dy, x + dx)
            if 0 <= n[0] < H and 0 <= n[1] < W and n not in seen and tkey[n[0]][n[1]] is not None:
                seen.add(n)
                todo.append(n)
    if exit_tile not in seen:
        raise SystemExit("the exit console on landing zone 2 cannot be reached from landing zone 1")
    print(f"LZ2 reachable from LZ1; {len(seen)} of {sum(k is not None for row in tkey for k in row)} open tiles "
          f"connected to the start")

    # ---- wall pieces along tile edges: (axis, line coordinate, start, end, front sector, back sector, texture)
    # Corner (i, j) of the tile grid is at Doom (i * UNIT, (H - j) * UNIT). The front side is on the right.
    pieces = collections.defaultdict(list)
    for r in range(H):
        for c in range(W):
            s = sector_of[r][c]
            if s is None:
                continue
            for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nr, nc = r + dr, c + dc
                inside = 0 <= nr < H and 0 <= nc < W
                t = sector_of[nr][nc] if inside else None
                if t == s:
                    continue
                if t is not None and (dr, dc) in ((0, -1), (-1, 0)):
                    continue     # two-sided edges are emitted once, from the tile on their left/top
                # the edge, walked so that tile (r, c) is on the right
                if dc == 1:
                    a, b = (c + 1, r), (c + 1, r + 1)    # east edge, walking down the screen (south)
                elif dc == -1:
                    a, b = (c, r + 1), (c, r)
                elif dr == 1:
                    a, b = (c + 1, r + 1), (c, r + 1)    # south edge, walking west
                else:
                    a, b = (c, r), (c + 1, r)
                tex = wall_texture(nr, nc) if t is None else None
                front, back = s, t
                kinds = (sectors[s][0], sectors[t][0] if t is not None else None)
                if t is not None and kinds[0] in ("door", "exit") and kinds[1] not in ("door", "exit"):
                    a, b, front, back = b, a, t, s      # doors and the exit console face outward
                axis = "v" if a[0] == b[0] else "h"
                fixed = a[0] if axis == "v" else a[1]
                lo, hi = (a[1], b[1]) if axis == "v" else (a[0], b[0])
                pieces[(axis, fixed, lo < hi, front, back, tex)].append((min(lo, hi), max(lo, hi)))

    # merge each group's touching pieces into runs
    runs = []
    for (axis, fixed, forward, front, back, tex), spans in pieces.items():
        spans.sort()
        cur = list(spans[0])
        for lo, hi in spans[1:]:
            if lo == cur[1]:
                cur[1] = hi
            else:
                runs.append((axis, fixed, forward, front, back, tex, cur[0], cur[1]))
                cur = [lo, hi]
        runs.append((axis, fixed, forward, front, back, tex, cur[0], cur[1]))
    # split runs wherever another run ends on them (no T-junctions)
    ends = set()
    for axis, fixed, forward, front, back, tex, lo, hi in runs:
        for p in (lo, hi):
            ends.add((fixed, p) if axis == "v" else (p, fixed))
    lines = []
    for axis, fixed, forward, front, back, tex, lo, hi in runs:
        cuts = [lo] + [p for p in range(lo + 1, hi) if ((fixed, p) if axis == "v" else (p, fixed)) in ends] + [hi]
        for p, q in zip(cuts, cuts[1:]):
            a = (fixed, p) if axis == "v" else (p, fixed)
            b = (fixed, q) if axis == "v" else (q, fixed)
            if not forward:
                a, b = b, a
            lines.append((a, b, front, back, tex))

    # ---- UDMF
    vertex_index, vertices = {}, []

    def vertex(corner):
        if corner not in vertex_index:
            vertex_index[corner] = len(vertices)
            vertices.append((corner[0] * UNIT, (H - corner[1]) * UNIT))
        return vertex_index[corner]

    out = ['namespace = "zdoom";']
    sides = []
    linedefs = []
    for a, b, front, back, tex in lines:
        v1, v2 = vertex(a), vertex(b)
        fk = sectors[front][0]
        bk = sectors[back][0] if back is not None else None
        if back is None:
            sides.append({"sector": front, "texturemiddle": tex})
            linedefs.append({"v1": v1, "v2": v2, "sidefront": len(sides) - 1, "blocking": True})
            continue
        line = {"v1": v1, "v2": v2, "twosided": True}
        cave = "RROCK18" in (sectors[front][3], sectors[back][3])
        top = DOOR_FACE if bk == "door" else (DEFAULT_WALL if cave else FACADE)
        bottom = EXIT_TEXTURE if bk == "exit" else "ROCK3"
        sides.append({"sector": front, "texturetop": top, "texturebottom": bottom})
        line["sidefront"] = len(sides) - 1
        sides.append({"sector": back, "texturetop": DOOR_TRACK if fk == "door" else (DEFAULT_WALL if cave else FACADE),
                      "texturebottom": "ROCK3"})
        line["sideback"] = len(sides) - 1
        if bk == "door":
            line.update({"special": 12, "arg0": 0, "arg1": 32, "arg2": 150, "playeruse": True,
                         "monsteruse": True, "repeatspecial": True})
        elif bk == "exit":
            line.update({"special": 243, "arg0": 0, "playeruse": True})
        linedefs.append(line)

    def block(kind, fields):
        body = []
        for k, v in fields.items():
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, str):
                v = '"' + v + '"'
            body.append(f"{k} = {v};")
        return f"{kind}\n{{\n" + "\n".join(body) + "\n}"

    things = []

    def thing(r, c, typ, angle=0, ox=0, oy=0):
        things.append({"x": c * UNIT + UNIT // 2 + ox, "y": (H - 1 - r) * UNIT + UNIT // 2 + oy, "angle": angle,
                       "type": typ, "skill1": True, "skill2": True, "skill3": True, "skill4": True, "skill5": True,
                       "single": True, "coop": True, "dm": True})

    def open_floor(r, c):
        return 0 <= r < H and 0 <= c < W and tkey[r][c] is not None and tkey[r][c][0] == "floor"

    def far_from_start(r, c, d=14):
        return (r - start[0]) ** 2 + (c - start[1]) ** 2 > d * d

    sr, sc = start
    thing(sr, sc, 1, 90)
    for i, (dr, dc) in enumerate(((0, 1), (0, -1), (1, 0))):   # co-op starts
        thing(sr + dr, sc + dc, 2 + i, 90)
    # xenos on some of the weed nodes, never right next to the start
    for r, c in find("/obj/effect/landmark/weed_node"):
        if open_floor(r, c) and far_from_start(r, c) and rnd.random() < XENO_DENSITY:
            table = CAVE_XENOS if zone(tiles[r][c][2]) == "cave" else XENOS
            thing(r, c, rnd.choices([t for t, _ in table], [w for _, w in table])[0], rnd.choice(range(0, 360, 45)))
    # the hive: eggs around each silo spawn, a pair of warriors guarding it
    for r, c in silos:
        for _ in range(6):
            er, ec = r + rnd.randint(-3, 3), c + rnd.randint(-3, 3)
            if open_floor(er, ec):
                thing(er, ec, rnd.choice(EGGS))
        for dr, dc in ((1, 1), (-1, -1)):
            if open_floor(r + dr, c + dc):
                thing(r + dr, c + dc, 69, 270)
    # the xeno starting spots: the Queen at the roomiest one, up to three Praetorians at others
    xstarts = [p for p in find("/obj/effect/landmark/start/job/xenomorph") if open_floor(*p)]

    def room(p):
        return sum(open_floor(p[0] + dr, p[1] + dc) for dr in range(-3, 4) for dc in range(-3, 4))
    xstarts.sort(key=room, reverse=True)
    chosen = []
    for p in xstarts:     # the map marks a whole patch of tiles; keep a few spots well apart
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 8 ** 2 for q in chosen):
            chosen.append(p)
    for i, (r, c) in enumerate(chosen[:4]):
        thing(r, c, 7 if i == 0 and room((r, c)) >= 45 else 64, 270)
    # Sons of Mars at some of the survivor spots, dead marines at the corpse spawners
    for r, c in find("/obj/effect/landmark/start/job/survivor"):
        if open_floor(r, c) and far_from_start(r, c) and rnd.random() < 0.45:
            thing(r, c, rnd.choice(SOM), rnd.choice(range(0, 360, 45)))
    for r, c in find("/obj/effect/landmark/corpsespawner"):
        if open_floor(r, c):
            thing(r, c, 15)
    # supplies
    for prefix, choices in (("/obj/effect/spawner/random/weaponry/gun", GUNS),
                            ("/obj/effect/spawner/random/weaponry/ammo", AMMO),
                            ("/obj/effect/spawner/random/weaponry/explosive", [2010]),
                            ("/obj/effect/spawner/random/medical", MEDICAL),
                            ("/obj/item/storage/firstaid", [2012]),
                            ("/obj/structure/reagent_dispensers/fueltank", [2035])):
        for r, c in find(prefix):
            if open_floor(r, c):
                thing(r, c, rnd.choice(choices))
    # a little help at the landing zone
    for i, typ in enumerate((2001, 2048, 2008, 2012, 2018)):
        thing(sr + 2, sc - 2 + i, typ)

    out += [block("vertex", {"x": float(x), "y": float(y)}) for x, y in vertices]
    out += [block("linedef", l) for l in linedefs]
    out += [block("sidedef", {"sector": s["sector"], **{k: v for k, v in s.items() if k != "sector"}}) for s in sides]
    out += [block("sector", {"heightfloor": fh, "heightceiling": ch, "texturefloor": ff, "textureceiling": cf,
                             "lightlevel": light}) for _, ff, fh, cf, ch, light in sectors]
    out += [block("thing", t) for t in things]
    textmap = ("\n".join(out) + "\n").encode("ascii")

    mapinfo = b"""map LV624 "LV-624"
{
	levelnum = 624
	music = "TGMCLOBY"
	sky1 = "SKY1"
	next = "EndTitle"
	par = 600
}

episode LV624
{
	name = "Operation: LV-624"
	key = "o"
}
"""
    lumps = [("MAPINFO", mapinfo), ("LV624", b""), ("TEXTMAP", textmap), ("ENDMAP", b"")]
    data, directory, pos = b"", b"", 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    with open(args.out, "wb") as f:
        f.write(struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory)
    counts = collections.Counter(t["type"] for t in things)
    print("things by type:", dict(sorted(counts.items())))
    print(f"wrote {args.out}: {W}x{H} tiles, {len(sectors)} sectors, {len(linedefs)} lines, {len(vertices)} vertices, "
          f"{len(things)} things ({sum(n for t, n in counts.items() if t in dict(XENOS + CAVE_XENOS) or t in (7, 64))} "
          f"xenos)")


if __name__ == "__main__":
    main()
