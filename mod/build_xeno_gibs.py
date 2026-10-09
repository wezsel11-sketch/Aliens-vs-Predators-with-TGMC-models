"""Build gib sprites for the alien enemies from TGMC's own gib animations (GZDoom/UZDoom).

Each caste's "gibbed" animation (the body bursting into acid) becomes a new sprite set XG?? with frames A-E
taken from across the animation and F = the remains (the caste's gib corpse, or the last frame). The frames
share one bounding box so the burst does not jump around, and keep the living sprite's pixel scale (the same
factor build_sprites.py uses for the caste's walk art). build_alien_attacks.py adds the XDeath states that
use them; a monster gibs when it dies from a big overkill (a rocket, a fuel tank, the BFG).
The same WAD holds ACPD A-C, the bubbling acid puddle (Effects.dmi "acid2") that Spitter acid leaves on the floor.

usage: build_xeno_gibs.py --sprites TGMC_SPRITES --freedoom SPRITES_DIR --playpal IWAD --out WAD
"""
import argparse
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doomlib as dl  # noqa: E402
from build_sprites import source_png_for  # noqa: E402

# sprite -> (caste sheet, walk state, gib state, gib corpse state or None, Doom prefix the caste replaces, scale)
GIBS = {
    "XGSP": ("spitter", "Spitter Walking", "gibbed-a", "gibbed-a-corpse", "TROO", 1.0),
    "XGRU": ("runner", "Runner Walking", "gibbed-a-runner", "gibbed-a-corpse-runner", "SARG", 0.85),
    "XGSH": ("shrike", "Shrike Walking", "gibbed-a", "gibbed-a-corpse", "HEAD", 1.0),
    "XGCR": ("crusher", "Crusher Walking", "gibbed-a", "gibbed-a-corpse", "BOSS", 1.0),
    "XGWA": ("warrior", "Warrior Walking", "gibbed-a", "gibbed-a-corpse", "BOS2", 1.0),
    "XGHU": ("hunter", "Hunter Walking", "Hunter Gibbed", "Hunter Gibs", "SKEL", 1.0),
    "XGBO": ("boiler", "Boiler Walking", "gibbed-a-boiler", None, "FATT", 1.0),
    "XGWI": ("widow", "Widow Walking", "gibbed-a", "gibbed-a-corpse", "BSPI", 1.0),
    "XGCA": ("carrier", "Carrier Walking", "gibbed-a", "gibbed-a-corpse", "PAIN", 1.0),
    "XGDR": ("dragon", "Dragon Walking", "gibbed-a", None, "CYBR", 1.0),
    "XGQU": ("queen", "Queen Walking", "gibbed-a", "gibbed-a-corpse", "SPID", 1.0),
    "XGPR": ("praetorian", "Praetorian Walking", "gibbed-a", "gibbed-a-corpse", "VILE", 1.0),
}
PICKS = (0.0, 0.2, 0.4, 0.6, 0.8)   # where in the gib animation frames A-E come from


def state_files(root, sheet, state):
    m = json.load(open(os.path.join(root, sheet, "manifest.json")))
    hit = [s for s in m["states"] if s["name"] == state]
    if not hit:
        raise KeyError(f"{sheet}:{state}")
    return [os.path.join(root, sheet, f) for f in hit[0]["files"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprites", required=True)
    ap.add_argument("--freedoom", required=True)
    ap.add_argument("--playpal", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pal = dl.load_palette(args.playpal)
    lumps = []
    for prefix, (sheet, walk, gib, corpse, doom_prefix, scale) in GIBS.items():
        walk_d0 = dl.crop_content(Image.open(state_files(args.sprites, sheet, walk)[0]))
        orig_a1 = Image.open(source_png_for(args.freedoom, doom_prefix, "A", 1))
        factor = orig_a1.height / walk_d0.height * scale
        anim = [Image.open(p).convert("RGBA") for p in state_files(args.sprites, sheet, gib)]
        frames = [anim[round(t * (len(anim) - 1))] for t in PICKS]
        frames.append(Image.open(state_files(args.sprites, sheet, corpse)[0]).convert("RGBA") if corpse else anim[-1])
        # one shared box for all frames, so the burst stays in place
        boxes = [f.getchannel("A").getbbox() for f in frames]
        box = (min(b[0] for b in boxes if b), min(b[1] for b in boxes if b),
               max(b[2] for b in boxes if b), max(b[3] for b in boxes if b))
        for letter, frame in zip("ABCDEF", frames):
            img = frame.crop(box)
            w, h = max(1, round(img.width * factor)), max(1, round(img.height * factor))
            img = img.resize((w, h), Image.NEAREST)
            lumps.append((f"{prefix}{letter}0", dl.encode_patch(w, h, dl.to_grid(img, pal), w // 2, h)))
        print(f"{prefix}: {sheet} {gib} ({len(anim)} frames) at x{factor:.2f}")
    # the acid puddle: drawn flat on the floor (FLATSPRITE), so anchored at its centre
    acid = state_files(args.sprites, "Effects", "acid2")
    for letter, index in zip("ABC", (0, 3, 6)):
        img = dl.crop_content(Image.open(acid[index]).convert("RGBA"))
        img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
        lumps.append((f"ACPD{letter}0", dl.encode_patch(img.width, img.height, dl.to_grid(img, pal),
                                                         img.width // 2, img.height // 2)))
    dl.build_wad(lumps, args.out)
    print(f"wrote {args.out} with {len(lumps)} lumps")


if __name__ == "__main__":
    main()
