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

## One-step build

    mod/build_all.sh <tgmc-checkout> <freedoom-checkout> <freedoom1.wad|freedoom2.wad> <out-dir>

Extracts the TGMC sheets, composites the humanoids, and builds every PWAD into
`<out-dir>/wads/`: the five actor sets (`xeno_troo`, `marine_player`,
`som_trooper`, `som_heavy`, `spitter_chaingunner`), `green_fireball`,
`ammo_pickups`, `weapon_pickups`, and the sound sets (`gun_sounds`,
`voice_sounds`). The steps below are what it runs.

Actor mapping: player = TGMC marine; imp (`TROO`) = Spitter (its fireballs are
recolored green, `green_fireball.wad`); zombieman (`POSS`) = SOM trooper with
V-31 rifle; shotgun guy (`SPOS`) = SOM heavy with V-51 shotgun; chaingunner
(`CPOS`) = Spitter. The SOM units wear a sleeved uniform, boots, gloves, black
modular armor and a helmet. The chaingunner only spawns in Freedoom 2 (Doom 2
monster).

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

   Recolor-only sprites (the fireball) use `build_recolor.py`.

   Attack frames reuse the walk poses (`--attack-frames EFG`). Death frames are
   single-rotation lumps (`X0`) built at the living sprite's pixel scale, so a
   corpse is not shrunk to fit Freedoom's short death frames:
   `--death-png` uses one image (TGMC's `Spitter Dead`), and `--death-tilt-src`
   tips a standing figure over from about 20 degrees to flat across the frames
   (the humans; the SOM units drop their weapon first). TGMC has no attack or
   death animations for these bodies.

4. **Build sound PWADs.** Doom monsters share sound slots, so `voice_sounds.wad`
   also carries a `DEHACKED` lump (`sound_slots.deh`, added with `--raw`) that
   points the chaingunner and imp at the alien sound slots (sight, active, death,
   pain), and `DSDMPAIN` is replaced with a xeno sound, so Spitters do not use
   the human voices. (The chaingunner's attack sound is hard-coded in the engine.) Converts OGG to Doom DMX sound lumps (11025 Hz, 8-bit,
   trimmed to `--max-seconds`):

       python3 build_sounds.py --map DSPISTOL=pistol.ogg DSSHOTGN=shotgun.ogg \
           --max-seconds 1.0 --out gun_sounds.wad

5. **Ammo and weapon pickups.** `build_ammo_pwad.py` replaces CLIP, SHEL, ROCK,
   and AMMO; `build_weapon_pickups.py` replaces SHOT, SGN2, MGUN, LAUN, PLAS, BFUG,
   and CSAW with TGMC gun art (CSAW uses the powered axe; TGMC has no chainsaw).
   Both scale from the Freedoom pickup and anchor with `buildcfg.txt` offsets.

6. **Not included: first-person weapon views.** TGMC has only side-view gun art;
   rotating it upright produced thin sticks that did not read as weapons, so
   Freedoom's own first-person sprites are kept.

## Testing

Load the WADs in a PrBoom-based engine after the IWAD. Use `dsda-doom`
(Debian/Ubuntu package `prboom-plus` provides the related engine). Do not use
Chocolate Doom: it shows a blocking `R_ProjectSprite: invalid sprite frame 28 : 13`
error for any PWAD that contains a sprite marker block (S_START/S_END), even an
empty one. The same WADs run cleanly in `dsda-doom`.

    dsda-doom -iwad freedoom1.wad -file <mod>.wad -warp 1 1

To see the actors up close, `build_testmap.py` copies a map from an IWAD and
adds one of each replaced actor in front of the player start (no geometry
changes, so no node builder is needed):

    python3 build_testmap.py freedoom2.wad testmap.wad --map MAP01 --distance 300
    dsda-doom -iwad freedoom2.wad -file testmap.wad <mod>.wad ... -warp 1

`doomlib.py` holds the shared palette, patch encoding, and PWAD writer. It has
no separate tests; the built WADs were checked by decoding the lumps and by
running them in `dsda-doom`.

## Palette matching

`doomlib.nearest_index` matches colors in CIE Lab with the lightness weight set to
0.8, not by RGB distance. With RGB distance the Spitter's yellow-green highlights
came out orange and brown, because Doom's palette has few yellow-greens. The
palette is read from the IWAD's PLAYPAL lump (see Inputs).

## Licenses

- TGMC code: AGPL-3.0. Art: mostly CC-BY-NC, some CC-BY-NC-SA and CC-BY-SA
  (see the table in the TGMC README). Attribute the artists.
- Freedoom: BSD-style (see its `COPYING.adoc`).
- Output mods built from these inputs are non-commercial.
