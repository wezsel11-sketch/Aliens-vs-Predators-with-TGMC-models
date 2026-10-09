"""Build a PWAD that replaces Doom's music with TGMC's (GZDoom/UZDoom only).

TGMC's repository holds one real song, the lobby theme (config/lobby_themes/DawsonChristian.ogg), plus the
RoboCop elevator tune and the ambience loops that play in rounds. They become:
  title screen, finale and text screens  <- lobby theme
  intermission (level tally)             <- elevator tune
  levels                                 <- lobby theme and the ambience loops, in rotation
Each track is stored once as an OGG lump (TGMCxxxx), loudness-normalized with ffmpeg's loudnorm and
re-encoded as Vorbis. An SNDINFO lump points every Doom 1 and Doom 2 music name at a track with
$musicalias, so the WAD stays small and works with freedoom1.wad and freedoom2.wad.

usage: build_music.py --tgmc TGMC_ROOT --out WAD
"""
import argparse
import os
import struct
import subprocess
import tempfile

# lump name -> (path in the TGMC checkout, target loudness in LUFS)
TRACKS = {
    "TGMCLOBY": ("config/lobby_themes/DawsonChristian.ogg", -16),
    "TGMCELEV": ("sound/music/elevator/robocop-short.ogg", -18),
    "TGMCSPAC": ("sound/ambience/ambispace.ogg", -20),
    "TGMCCAVE": ("sound/ambience/ambicave2.ogg", -20),
    "TGMCMINE": ("sound/ambience/ambimine.ogg", -20),
    "TGMCMOON": ("sound/ambience/ambimo1.ogg", -20),
    "TGMCLAVA": ("sound/ambience/ambilava1.ogg", -20),
    "TGMCSNOW": ("sound/ambience/ambi_snow.ogg", -20),
    "TGMCSHIP": ("sound/ambience/shipambience.ogg", -20),
    "TGMCDERE": ("sound/effects/urban/indoors/derelict_ambience.ogg", -20),
    "TGMCURBN": ("sound/effects/urban/indoors/urban_interior.ogg", -20),
}
LEVEL_ROTATION = ["TGMCLOBY", "TGMCSPAC", "TGMCCAVE", "TGMCSHIP", "TGMCMINE", "TGMCDERE", "TGMCLAVA",
                  "TGMCMOON", "TGMCURBN", "TGMCSNOW"]
SCREENS = {"D_DM2TTL": "TGMCLOBY", "D_INTRO": "TGMCLOBY", "D_INTROA": "TGMCLOBY", "D_READ_M": "TGMCLOBY",
           "D_VICTOR": "TGMCLOBY", "D_BUNNY": "TGMCLOBY", "D_DM2INT": "TGMCELEV", "D_INTER": "TGMCELEV"}
DOOM2_LEVELS = ("runnin stalks countd betwee doom the_da shawn ddtblu in_cit dead stlks2 theda2 doom2 ddtbl2 "
                "runni2 dead2 stlks3 romero shawn2 messag count2 ddtbl3 ampie theda3 adrian messg2 romer2 "
                "tense shawn3 openin evil ultima").split()
DOOM1_LEVELS = [f"e{e}m{m}" for e in range(1, 5) for m in range(1, 10)]


def encode(path, lufs):
    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
                        "-ar", "44100", "-c:a", "libvorbis", "-q:a", "3", tmp.name], check=True)
        return open(tmp.name, "rb").read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tgmc", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    lumps = []
    for name, (rel, lufs) in TRACKS.items():
        data = encode(os.path.join(args.tgmc, rel), lufs)
        lumps.append((name, data))
        print(f"{name}: {rel} ({len(data) // 1024} KB)")
    aliases = dict(SCREENS)
    for levels in (DOOM2_LEVELS, DOOM1_LEVELS):
        for i, lvl in enumerate(levels):
            aliases[f"D_{lvl.upper()}"] = LEVEL_ROTATION[i % len(LEVEL_ROTATION)]
    sndinfo = "// Doom music names -> TGMC tracks (build_music.py)\n" + \
        "".join(f"$musicalias {k} {v}\n" for k, v in aliases.items())
    lumps.append(("SNDINFO", sndinfo.encode("ascii")))

    data, directory, pos = b"", b"", 12
    for name, body in lumps:
        directory += struct.pack("<II8s", pos, len(body), name.encode("ascii").ljust(8, b"\0"))
        data += body
        pos += len(body)
    with open(args.out, "wb") as f:
        f.write(struct.pack("<4sII", b"PWAD", len(lumps), 12 + len(data)) + data + directory)
    print(f"wrote {args.out}: {len(TRACKS)} tracks, {len(aliases)} music aliases")


if __name__ == "__main__":
    main()
