"""Build a PWAD with TGMC's title screens, menu logo and texts.

Pictures (TGMC lobby art, icons/misc/lobby_art/*.dmi, 608x480 = 4:3 like Doom's 320x200 screen):
  TITLEPIC <- som_doomguy (TGMC's own Doom-cover parody)
  CREDIT   <- tgmcpropaganda (shown in the title loop)
  INTERPIC <- marinesonlvriver (intermission background)
  M_DOOM   <- the TGMC eagle from tgmclogo plus "TGMC" lettering (Pillow's built-in font), at Freedoom's size
HELP (Doom 2) and HELP1 (Doom 1) are redrawn as a TGMC "field manual": the TGMC pickups (read from the built
pickup WADs, --wads) labelled in Freedoom's small HUD font, over a darkened lobby-art picture.
A DEHACKED [STRINGS] block renames the levels after TGMC maps (Freedoom 1 and 2), and replaces pickup
messages, death messages, monster and weapon names, the Doom 2 cast call, skill names, quit messages and the
story screens (TGMC mission briefings and after-action reports, over a dark weed floor). It is
DEHACKED and not LANGUAGE because Freedoom sets these strings in its own DEHACKED lump, which outranks any
LANGUAGE lump; a later DEHACKED lump overrides it. A MAPINFO lump sets GameInfo forcetextinmenus, so GZDoom/UZDoom
show the skill and episode names as text. The intermission screen always prefers the level-name graphics
(CWILV00-31 for Doom 2, WILVem for Doom 1), so those are redrawn with the TGMC names in Freedoom's own font
(graphics/text/fontchars in the Freedoom checkout).

usage: build_presentation.py --tgmc TGMC_ROOT --freedoom FREEDOOM_ROOT --playpal IWAD --wads WAD_DIR --out WAD
"""
import argparse
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from extract_dmi import read_description  # noqa: E402

ART = "icons/misc/lobby_art"
SCREENS = {"TITLEPIC": "som_doomguy", "CREDIT": "tgmcpropaganda", "INTERPIC": "marinesonlvriver"}
LOGO_SIZE = (159, 37)          # Freedoom's M_DOOM, so the main menu keeps its layout
LOGO_OFFSETS = (13, -16)

DOOM2_MAPS = ["LV-624", "Big Red", "Ice Colony", "Prison Station", "Fiorina Science Annex", "Kutjevo Refinery",
              "Lawanka Outpost", "Chigusa", "Magmoor Digsite IV", "Desparity", "Research Outpost",
              "Orion Military Outpost", "Oscar Outpost", "Whiskey Outpost", "Delta Station", "Gelida IV",
              "Icy Caves", "Lava Outpost", "Metnal Mining Operation", "Vapor Processing", "Slumbridge",
              "Meridian Riptide", "Daedalus Prison", "CORSAT Research Station", "LV-759",
              "Bluesummers Wreck Site", "Blue Moon", "Arachne", "Iteron", "Pillar of Spring", "Fort Phobos",
              "Combat Patrol Base"]
DOOM1_MAPS = ["Theseus", "LV-624", "Big Red", "Ice Colony", "Prison Station", "Kutjevo Refinery", "Lawanka Outpost",
              "Chigusa", "Fort Phobos",
              "Magmoor Digsite IV", "Desparity", "Research Outpost", "Orion Military Outpost", "Oscar Outpost",
              "Whiskey Outpost", "Delta Station", "Gelida IV", "Icy Caves",
              "Lava Outpost", "Metnal Mining Operation", "Vapor Processing", "Slumbridge", "Meridian Riptide",
              "Daedalus Prison", "CORSAT Research Station", "LV-759", "Combat Patrol Base",
              "Bluesummers Wreck Site", "Blue Moon", "Arachne", "Iteron", "Pillar of Spring", "Legacy of Spring",
              "Fiorina Science Annex", "Sulaco", "The Hive"]
EPISODES = {"TXT_D1E1": "Planetside Assault", "TXT_D1E2": "Hive Infestation", "TXT_D1E3": "Sons of Mars",
            "TXT_D1E4": "The Queen's Nest", "TXT_D2E1": "TerraGov Marine Corps"}

TEXTS = {
    # skills
    "SKILL_BABY": "Recruit", "SKILL_EASY": "Private", "SKILL_NORMAL": "Squad Leader", "SKILL_HARD": "Veteran",
    "SKILL_NIGHTMARE": "Game Over, Man!",
    # quit messages
    "QUITMSG": "The hive grows stronger\nevery minute you're gone.\nPress Y to abandon the marines.",
    "QUITMSG1": "Retreat? The Queen\nwill be pleased.",
    "QUITMSG2": "Your squad still needs you,\nmarine. Quit anyway?",
    "QUITMSG3": "Press N to keep\npurging xenos.\nPress Y to desert.",
    "QUITMSG4": "Desertion is a court-martial\noffense. Are you sure?",
    "QUITMSG5": "The xenos never sleep.\nWill you?",
    "QUITMSG6": "Game over, man!\nGame over!",
    "QUITMSG7": "The Sons of Mars will\ntake this colony without you.",
    "QUITMSG8": "Leaving the operation?\nCommand will hear about this.",
    "QUITMSG9": "Don't go! There's a facehugger\nunder your desk!",
    "QUITMSG10": "Your dropship is leaving.\nAre you on it?",
    "QUITMSG11": "Press Y to let the hive\nspread across the colony.",
    "QUITMSG12": "Quit now and the larva\nwins. Are you sure?",
    "QUITMSG13": "Even the requisitions officer\nis disappointed in you.",
    "QUITMSG14": "Not even staying for\nanother drop?",
    # pickups
    "GOTARMOR": "Put on M3 pattern marine armor.",
    "GOTMEGA": "Put on M5 riot armor!",
    "GOTHTHBONUS": "Swallowed a bicaridine pill.",
    "GOTARMBONUS": "Picked up an M10 helmet.",
    "GOTSTIM": "Injected a bicaridine autoinjector.",
    "GOTMEDINEED": "Bandaged up. You REALLY needed that!",
    "GOTMEDIKIT": "Bandaged your wounds with gauze.",
    "GOTSUPER": "Advanced first-aid kit!",
    "GOTMSPHERE": "O2 first-aid kit!",
    "GOTBLUECARD": "Picked up a blue ID card.", "GOTYELWCARD": "Picked up a yellow ID card.",
    "GOTREDCARD": "Picked up a red ID card.", "GOTBLUESKUL": "Picked up a blue access card.",
    "GOTYELWSKUL": "Picked up a yellow access card.", "GOTREDSKUL": "Picked up a red access card.",
    "GOTINVUL": "Bomb suit! Nearly indestructible.",
    "GOTBERSERK": "Bezerk kit!",
    "GOTINVIS": "Xeno costume! They can't tell you apart.",
    "GOTSUIT": "Radiation suit.",
    "GOTMAP": "Tactical tablet: area map downloaded.",
    "GOTVISOR": "Night-vision goggles.",
    "GOTCLIP": "Picked up a rifle magazine.", "GOTCLIPBOX": "Picked up a box of magazines.",
    "GOTROCKET": "Picked up an RPG round.", "GOTROCKBOX": "Picked up a crate of rockets.",
    "GOTCELL": "Picked up a plasma cell.", "GOTCELLBOX": "Picked up a powerpack.",
    "GOTSHELLS": "Picked up some buckshot.", "GOTSHELLBOX": "Picked up a box of buckshot.",
    "GOTBACKPACK": "Picked up a marine backpack full of ammo!",
    "GOTSHOTGUN": "You got the SH-35 shotgun!", "GOTSHOTGUN2": "You got a double-barreled shotgun!",
    "GOTCHAINGUN": "You got the MG-60 machine gun!", "GOTLAUNCHER": "You got an RPG launcher!",
    "GOTPLASMA": "You got a plasma rifle!", "GOTBFG9000": "You got the plasma cannon! Oh, yes.",
    "GOTCHAINSAW": "A powered axe! Time to cut some xenos.",
    "TAG_SHOTGUN": "SH-35 Shotgun", "TAG_SUPERSHOTGUN": "Double-Barreled Shotgun", "TAG_CHAINGUN": "MG-60 Machine Gun",
    "TAG_ROCKETLAUNCHER": "RPG Launcher", "TAG_PLASMARIFLE": "Plasma Rifle", "TAG_BFG9000": "Plasma Cannon",
    "TAG_CHAINSAW": "Powered Axe",
    # death messages
    "OB_ZOMBIE": "%o was gunned down by a Sons of Mars trooper.",
    "OB_SHOTGUY": "%o was blasted by a Sons of Mars heavy.",
    "OB_CHAINGUY": "%o was melted by a Spitter's acid.",
    "OB_IMP": "%o was melted by a Spitter.", "OB_IMPHIT": "%o was slashed by a Spitter.",
    "OB_DEMONHIT": "%o was torn apart by a Runner.", "OB_SPECTREHIT": "%o never saw the Runner coming.",
    "OB_SKULL": "%o was facehugged.",
    "OB_CACO": "%o was spat on by a Shrike.", "OB_CACOHIT": "%o was ripped up by a Shrike.",
    "OB_BARON": "%o was spat on by a Crusher.", "OB_BARONHIT": "%o was trampled by a Crusher.",
    "OB_KNIGHT": "%o was spat on by a Warrior.", "OB_KNIGHTHIT": "%o was punched out by a Warrior.",
    "OB_UNDEAD": "%o was hunted down by a Hunter.", "OB_UNDEADHIT": "%o was ambushed by a Hunter.",
    "OB_FATSO": "%o was bombarded by a Boiler.", "OB_BABY": "%o was dissolved by a Widow.",
    "OB_VILE": "%o was burned by a Praetorian's acid.", "OB_SPIDER": "%o was executed by the Queen.",
    "OB_CYBORG": "%o was incinerated by a Dragon.",
}
# Story screens between episodes (Freedoom 1: E1-E4) and between Doom 2 chapters (C1-C6), and their background:
# TGMCSTRY, a dark weed floor from hive_textures.wad.
STORY = {
    "E1TEXT": "The colony is quiet again. Your squad\nclawed its way from the landing zone\nthrough every corridor of the outpost.\n\n"
              "But the distress beacon is still\nscreaming, and the tunnels under the\ncolony go deeper than any map shows.\n\n"
              "Command has a new order: go down there.",
    "E2TEXT": "You found the hive. Resin coated the\nwalls, eggs lined the floors, and the\nthings that crawled out of them never\n"
              "stopped coming.\n\nYou burned the nest and fought your way\nback to the surface. On the horizon a\n"
              "Sons of Mars dropship is landing.\nSomeone else wants this planet too.",
    "E3TEXT": "The Sons of Mars wanted the xenos for\nthemselves: cages, pens, a whole base\nbuilt to breed them into weapons.\n\n"
              "Their base is ash now. But the cages\nare empty, and the trail of acid leads\nto the one place nobody came back\n"
              "from: the Queen's nest.",
    "E4TEXT": "The Queen is dead. Her screech still\nrings in your ears as the dropship\nlifts off the burning colony.\n\n"
              "The hive is silent. The marines who\nmade it out sit quietly in the cargo\nbay, counting the ones who didn't.\n\n"
              "Game over, man? Not today.\nTerraGov Marine Corps: mission complete.",
    "C1TEXT": "You punched through the outer\ncolonies. Every outpost tells the same\nstory: barricades, empty magazines,\n"
              "and resin creeping over the walls.\n\nThe infestation is spreading faster\nthan Command thought. Push on.",
    "C2TEXT": "Deep in the research wing you find\nthe logs. Someone brought the first\negg here on purpose.\n\n"
              "The logs carry a Sons of Mars seal.\nThe next drop takes you to their\nmining operations.",
    "C3TEXT": "The Sons of Mars are finished here,\nbut their work is not. Every tunnel\nyou clear leads deeper into the hive.\n\n"
              "The ground itself is alive now.\nSomewhere below, the Queen is waiting.",
    "C4TEXT": "The Queen's nest burns behind you.\nThe screeching stops. For the first\ntime since the drop, the colony is\nquiet.\n\n"
              "The dropship is waiting at the landing\nzone. You walk, you don't run.\nYou've earned that.\n\n"
              "TerraGov Marine Corps: mission complete.",
    "C5TEXT": "A hidden transmission points you to\nFort Phobos, a base the colony maps\ndon't show. Something there is still\n"
              "broadcasting. Go and see what it is.",
    "C6TEXT": "Fort Phobos held one last secret: a\ncombat patrol base, overrun but not\nlost. Clear it, and the sector is yours.",
}
STORY_BACKGROUND = "TGMCSTRY"
BGFLATS = ["BGFLATE1", "BGFLATE2", "BGFLATE3", "BGFLATE4", "BGFLAT06", "BGFLAT11", "BGFLAT20", "BGFLAT30",
           "BGFLAT15", "BGFLAT31"]

NAMES = {"ZOMBIE": "Sons of Mars Trooper", "SHOTGUN": "Sons of Mars Heavy", "HEAVY": "Spitter", "IMP": "Spitter",
         "DEMON": "Runner", "LOST": "Facehugger", "CACO": "Shrike", "HELL": "Warrior", "BARON": "Crusher",
         "ARACH": "Widow", "PAIN": "Carrier", "REVEN": "Hunter", "MANCU": "Boiler", "ARCH": "Praetorian",
         "SPIDER": "Queen", "CYBER": "Dragon"}


def freedoom_text(fontdir, text):
    """Render text with Freedoom's big font glyphs (fontchars/fontNNN.png, by character code), white."""
    glyphs = []
    for c in text:
        path = os.path.join(fontdir, "font%03d.png" % ord(c))
        glyphs.append(Image.open(path).convert("RGBA") if c != " " and os.path.exists(path) else None)
    width = sum(g.width if g else 7 for g in glyphs)
    height = max(g.height for g in glyphs if g)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for g in glyphs:
        if g:
            out.alpha_composite(g, (x, height - g.height))
        x += g.width if g else 7
    return out


def level_name_patches(fontdir, pal):
    """Intermission level-name graphics with the TGMC names."""
    def patch(text):
        img = freedoom_text(fontdir, text)
        img.putalpha(img.getchannel("A").point(lambda v: 255 if v > 100 else 0))
        return dl.encode_patch(img.width, img.height, dl.to_grid(img, pal), 0, 0)
    lumps = [(f"CWILV{i:02d}", patch(name)) for i, name in enumerate(DOOM2_MAPS)]
    lumps += [(f"WILV{i // 9}{i % 9}", patch(name)) for i, name in enumerate(DOOM1_MAPS)]
    return lumps


HELP_BACKGROUND = "marinesonlvriver"
# rows of (label, pickup sprites); every sprite comes from the built pickup WADs
HELP_ROWS = [
    [("Weapons", ["CSAWA0", "SHOTA0", "SGN2A0", "MGUNA0", "LAUNA0", "PLASA0", "BFUGA0"])],
    [("Bullets", ["CLIPA0", "AMMOA0"]), ("Shells", ["SHELA0", "SBOXA0"]), ("Backpack", ["BPAKA0"])],
    [("Rockets", ["ROCKA0", "BROKA0"]), ("Cells", ["CELLA0", "CELPA0"]), ("Berserk", ["PSTRA0"])],
    [("Medical", ["BON1A0", "STIMA0", "MEDIA0"]), ("Armor", ["BON2A0", "ARM1A0", "ARM2A0"])],
    [("Big kits", ["SOULA0", "MEGAA0"]), ("Tablet", ["PMAPA0"]), ("Goggles", ["PVISA0"])],
    [("Rad suit", ["SUITA0"]), ("Costume", ["PINSA0"]), ("Bomb suit", ["PINVA0"]),
     ("Keys", ["BKEYA0", "RKEYA0", "YKEYA0"])],
]
HELP_WADS = ["weapon_pickups.wad", "ammo_pickups.wad", "item_pickups.wad"]


def wad_lumps(path):
    d = open(path, "rb").read()
    n, off = struct.unpack("<4xII", d[:12])
    out = {}
    for i in range(n):
        p, size, name = struct.unpack("<II8s", d[off + 16 * i:off + 16 * i + 16])
        out[name.rstrip(b"\0").decode()] = d[p:p + size]
    return out


def decode_patch(b, pal):
    """A Doom patch lump as an RGBA image in palette colours."""
    w, h = struct.unpack("<hh", b[:4])
    offs = struct.unpack("<%dI" % w, b[8:8 + 4 * w])
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for x, o in enumerate(offs):
        while b[o] != 0xFF:
            top, length = b[o], b[o + 1]
            for k in range(length):
                px[x, top + k] = tuple(pal[b[o + 3 + k]]) + (255,)
            o += 4 + length
    return img


def small_text(graphics, text):
    """Text in Freedoom's small HUD font (graphics/stcfnNNN.png, upper case, red)."""
    glyphs = [Image.open(os.path.join(graphics, "stcfn%03d.png" % ord(c))).convert("RGBA") if c != " " else None
              for c in text.upper()]
    width = sum(g.width if g else 4 for g in glyphs)
    out = Image.new("RGBA", (width, max(g.height for g in glyphs if g)), (0, 0, 0, 0))
    x = 0
    for g in glyphs:
        if g:
            out.alpha_composite(g, (x, 0))
        x += g.width if g else 4
    return out


def help_page(tgmc, freedoom, wads, pal):
    sprites = {}
    for name in HELP_WADS:
        sprites.update(wad_lumps(os.path.join(wads, name)))
    graphics = os.path.join(freedoom, "graphics")
    page = ImageEnhance.Brightness(lobby_art(tgmc, HELP_BACKGROUND).convert("RGB").resize((320, 200), Image.LANCZOS))
    page = page.enhance(0.35).convert("RGBA")
    title = freedoom_text(os.path.join(graphics, "text", "fontchars"), "Field Manual")
    page.alpha_composite(title, ((320 - title.width) // 2, 2))
    y, row_h = 21, 30
    for row in HELP_ROWS:
        sections = []
        for label, names in row:
            items = [dl.crop_content(decode_patch(sprites[n], pal)) for n in names]
            sections.append((small_text(graphics, label), items))
        tallest = max(i.height for _, items in sections for i in items)
        k = min(1.0, (row_h - 10) / tallest)
        for _ in range(20):   # shrink until the row fits the screen width
            width = sum(max(t.width, sum(round(i.width * k) + 3 for i in items)) + 10 for t, items in sections)
            if width <= 314:
                break
            k *= 0.9
        x = 3 + (314 - width) // 2
        for text, items in sections:
            page.alpha_composite(text, (x, y))
            ix = x
            for item in items:
                item = item.resize((max(1, round(item.width * k)), max(1, round(item.height * k))), Image.NEAREST)
                page.alpha_composite(item, (ix, y + row_h - 1 - item.height))
                ix += item.width + 3
            x = max(x + text.width, ix) + 10
        y += row_h
    return dl.encode_patch(320, 200, dl.to_grid(page, pal), 0, 0)


def lobby_art(tgmc, name):
    """The first frame of a lobby-art .dmi (a single full-size PNG frame)."""
    path = os.path.join(tgmc, ART, name + ".dmi")
    desc = read_description(path)
    w = int(desc.split("width = ")[1].split()[0])
    h = int(desc.split("height = ")[1].split()[0])
    return Image.open(path).convert("RGBA").crop((0, 0, w, h))


def screen(img, pal):
    img = img.convert("RGB").resize((320, 200), Image.LANCZOS).convert("RGBA")
    return dl.encode_patch(320, 200, dl.to_grid(img, pal), 0, 0)


def logo(tgmc, pal):
    """The TGMC eagle emblem (its blue background removed) beside 'TGMC' lettering."""
    full = lobby_art(tgmc, "tgmclogo")
    bg = full.getpixel((4, 4))[:3]
    px = full.load()
    for y in range(full.height):
        for x in range(full.width):
            r, g, b, a = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 60:
                px[x, y] = (0, 0, 0, 0)
    emblem = dl.crop_content(full)
    h = LOGO_SIZE[1]
    emblem = emblem.resize((round(emblem.width * h / emblem.height), h), Image.LANCZOS)
    out = Image.new("RGBA", LOGO_SIZE, (0, 0, 0, 0))
    out.alpha_composite(emblem, (0, 0))
    font = ImageFont.load_default(size=40)
    d = ImageDraw.Draw(out)
    x = emblem.width + 6
    d.text((x, -6), "TGMC", font=font, fill=(235, 190, 70, 255), stroke_width=2, stroke_fill=(40, 30, 10, 255))
    # keep only solid pixels (Doom patches have no partial transparency)
    out.putalpha(out.getchannel("A").point(lambda v: 255 if v > 100 else 0))
    return dl.encode_patch(LOGO_SIZE[0], LOGO_SIZE[1], dl.to_grid(out, pal), *LOGO_OFFSETS)


def strings():
    """(key, text) pairs for every replaced string."""
    pairs = [(f"HUSTR_{i}", f"MAP{i:02d}: {name}") for i, name in enumerate(DOOM2_MAPS, 1)]
    pairs += [(f"HUSTR_E{i // 9 + 1}M{i % 9 + 1}", f"E{i // 9 + 1}M{i % 9 + 1}: {name}") for i, name in enumerate(DOOM1_MAPS)]
    pairs += list(EPISODES.items()) + list(TEXTS.items())
    for k, v in NAMES.items():
        pairs += [(f"CC_{k}", v), (f"FN_{k}", v)]
    pairs += list(STORY.items()) + [(k, STORY_BACKGROUND) for k in BGFLATS]
    return pairs + [("FN_SPECTRE", "Stalking Runner"), ("CC_HERO", "Our Marine")]


def dehacked():
    lines = ["Patch File for DeHackEd v3.0", "Doom version = 19", "Patch format = 6", "",
             "# TGMC texts (build_presentation.py)", "[STRINGS]"]
    lines += [f"{k} = {v.replace(chr(10), chr(92) + 'n')}" for k, v in strings()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_wad(lumps, out):
    data, directory, pos = b"", b"", 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    with open(out, "wb") as f:
        f.write(struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tgmc", required=True)
    ap.add_argument("--freedoom", required=True, help="Freedoom checkout (its big font glyphs are used)")
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--wads", required=True, help="the built WADs (pickup sprites for the help page)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    assert len(DOOM2_MAPS) == 32 and len(DOOM1_MAPS) == 36 and len(set(DOOM1_MAPS)) == 36
    pal = dl.load_palette(args.playpal)
    lumps = [(lump, screen(lobby_art(args.tgmc, art), pal)) for lump, art in SCREENS.items()]
    lumps.append(("M_DOOM", logo(args.tgmc, pal)))
    page = help_page(args.tgmc, args.freedoom, args.wads, pal)
    lumps += [("HELP", page), ("HELP1", page)]
    lumps += level_name_patches(os.path.join(args.freedoom, "graphics", "text", "fontchars"), pal)
    lumps.append(("DEHACKED", dehacked()))
    lumps.append(("MAPINFO", b"GameInfo\n{\n  forcetextinmenus = true\n}\n"))
    write_wad(lumps, args.out)
    print(f"wrote {args.out}: {len(lumps)} lumps")


if __name__ == "__main__":
    main()
