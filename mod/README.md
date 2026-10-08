# Doom mod build scripts

Scripts that turn TGMC (BYOND/DM) sprites and sounds into a Doom PWAD that
overrides Freedoom's actors. Only the code is in this repo. The art, the
built WADs, and the extracted sprites are not, because they are third-party
material.

## Inputs

- A TGMC checkout: https://github.com/tgstation/terragov-marine-corps
  (the `.dmi` files under `icons/`, the OGG files under `sound/`)
- A Freedoom checkout: https://github.com/freedoom/freedoom
  (`sprites/`, `buildcfg.txt`, `lumps/playpal/playpal`)
- Freedoom IWADs to play with: `freedoom1.wad`, `freedoom2.wad`. Pass an IWAD as
  `--playpal`; the palette is read from its PLAYPAL lump. Do not use Freedoom's
  `lumps/playpal/playpal` file, which is not the real lump and gives wrong colors.
- Python 3 with Pillow, and ffmpeg (for `build_sounds.py`)

## Pipeline

1. **Extract** each TGMC `.dmi` into per-state, per-direction PNGs with a
   manifest:

       python3 extract_dmi.py <tgmc-root> <out-dir> icons/Xeno/castes/runner.dmi

   Output: `<out-dir>/<sheet>/manifest.json` and one PNG per frame.

2. **Composite** humanoids (body parts plus gear) per direction. `compose_units.py`
   expects the extracted `r_human` sheet under `tgmc_sprites/` next to it:

       python3 compose_units.py <outdir> x:som_armor:som_medium_black x:som_helmets:som_helmet_black

3. **Build sprite PWADs.** Replaces four walking frames (A-D) of a Freedoom
   actor with four direction images (S, N, E, W), mapped to Doom's 8 rotations.
   Anchors come from Freedoom's `buildcfg.txt`:

       python3 build_sprites.py --prefix POSS --frames ABCD \
           --d0 S.png --d1 N.png --d2 E.png --d3 W.png \
           --freedoom <freedoom>/sprites --buildcfg <freedoom>/buildcfg.txt \
           --playpal /usr/share/games/doom/freedoom1.wad --out som_trooper.wad

   Prefixes used: `PLAY` (player), `TROO` (imp), `POSS` (zombieman),
   `SPOS` (shotgun guy), `CPOS` (chaingunner).

   Attack frames reuse the walk poses (`--attack-frames EFG`). Death frames
   are single-rotation lumps (`X0`) from one image (`--death-frames ... --death-png`):
   TGMC's `Runner Dead` / `Spitter Dead`, or the standing composite rotated 90
   degrees for the humans. TGMC has no attack or death animations for these bodies.

4. **Build sound PWADs.** Converts OGG to Doom DMX sound lumps (11025 Hz, 8-bit,
   trimmed to `--max-seconds`):

       python3 build_sounds.py --map DSPISTOL=pistol.ogg DSSHOTGN=shotgun.ogg \
           --max-seconds 1.0 --out gun_sounds.wad

5. **Ammo pickups.** `build_ammo_pwad.py` replaces CLIP, SHEL, ROCK, and AMMO
   with TGMC art, scaled from the Freedoom pickup and anchored with
   `buildcfg.txt` offsets. Input: an extracted TGMC sheet directory.

## Testing

Load the WADs in a PrBoom-based engine after the IWAD. Use `dsda-doom`
(Debian/Ubuntu package `prboom-plus` provides the related engine). Do not use
Chocolate Doom: it shows a blocking `R_ProjectSprite: invalid sprite frame 28 : 13`
error for any PWAD that contains a sprite marker block (S_START/S_END), even an
empty one. The same WADs run cleanly in `dsda-doom`.

    dsda-doom -iwad freedoom1.wad -file <mod>.wad -warp 1 1

`doomlib.py` holds the shared palette, patch encoding, and PWAD writer. It has
no separate tests; the built WADs were checked by decoding the lumps and by
running them in `dsda-doom`.

## Licenses

- TGMC code: AGPL-3.0. Art: mostly CC-BY-NC, some CC-BY-NC-SA and CC-BY-SA
  (see the table in the TGMC README). Attribute the artists.
- Freedoom: BSD-style (see its `COPYING.adoc`).
- Output mods built from these inputs are non-commercial.
