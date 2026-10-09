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
- Python 3 with Pillow (10.1 or newer, for its built-in scalable font) and numpy, and ffmpeg (for `build_sounds.py`
  and `build_music.py`)

## One-step build

    mod/build_all.sh <tgmc-checkout> <freedoom-checkout> <freedoom1.wad|freedoom2.wad> <out-dir>

Extracts the TGMC sheets, composites the humanoids, and builds every PWAD into
`<out-dir>/wads/`: the five actor sets (`xeno_troo`, `marine_player`,
`som_trooper`, `som_heavy`, `spitter_chaingunner`), `green_fireball`,
`ammo_pickups`, `weapon_pickups`, `item_pickups`, `fuel_tank`, `xeno_gibs`, `hud_face`, the twelve `alien_*` enemy sets, `som_variants`, the sound sets (`gun_sounds`,
`heavy_gun_sounds`, `voice_sounds`, `alien_sounds`, `extra_sounds`, `marine_voice`, `hive_ambience`), `music`,
`presentation`, `hive_textures`, and the optional `weapon_view_voxel`. The steps below are what it runs.

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
   `build_item_pickups.py` does the same for armor and health: green armor = M3 marine armor,
   blue armor = M5 riot armor, armor bonus = M10 helmet, stimpack = bicaridine autoinjector,
   medikit = roll of gauze, health bonus = a red (bicaridine) pill. Armor blinks and the bonuses
   pulse by brightening the frames. These icons come from `icons/obj/...`, whose sheet names
   (`marine_armor`, `marine_helmets`) clash with the mob sheets, so `build_all.sh` extracts them
   into `tgmc_sprites/obj_items/`.

6. **First-person weapons: Freedoom's by default.** TGMC has only small side-view gun
   art, with nothing showing a gun from behind. Several attempts to build the rear view
   (rotated icons, voxel models, ray-marched smooth models, and a Blender/Cycles test
   that was not committed) read worse at Doom's 320x200 than Freedoom's hand-drawn guns,
   so those are kept. The voxel guns are an optional WAD (see below).

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

## More enemies, SOM variants, first-person weapons

- **Alien enemies** (`build_aliens.sh`): the rest of Doom's monsters become TGMC xeno castes, one WAD each:
  Pinky/Spectre = Runner, Lost Soul = facehugger, Cacodemon = Shrike, Baron = Crusher,
  Hell Knight = Warrior, Revenant = Hunter, Mancubus = Boiler, Arachnotron = Widow,
  Pain Elemental = Carrier, Cyberdemon = Dragon, Spiderdemon = Queen, Archvile = Praetorian. Every rotating
  frame (walk, attack, pain) uses the caste's 4-direction walk art, and the single-rotation frames
  (death, explosion) use its "Dead" image, via `build_sprites.py --auto-frames`. Frames that Freedoom stores in
  a shared picture (`skela1d1.png` holds frames A and D) are all found. The Archvile's attack, pain and resurrect
  frames are single-rotation too, so `--front-frames` gives them the living front view instead of the corpse; its
  flame is recoloured green (an acid burst). Freedoom's file names write the frame after `[` as `^`; the lump is
  named with `\` as Doom expects.
- **SOM variants** (`build_som_variants.py`, **GZDoom/UZDoom only**): five looks (light, medium, heavy,
  leader, officer) for both the zombieman and shotgun guy slots, each with its own armor and weapon.
  The script writes sprite sets `SOMA`..`SOME` and `SOSA`..`SOSE`, one DECORATE actor per look, and a
  `RandomSpawner` that replaces `ZombieMan` / `ShotgunGuy`, so each spawn picks a look at random. Output:
  `wads/som_variants.wad`. Load it instead of `som_trooper.wad` / `som_heavy.wad`.
- **Optional voxel first-person weapons** (`build_weapon_view.py`, `gun_models.py`, `voxel_gun.py`, output
  `weapon_view_voxel.wad`, not loaded by default): each weapon is a small hand-built voxel model (stock, receiver,
  barrel, magazine, sights, gloved forearms) sized after the TGMC icons and coloured like them, rendered from
  behind and above so the gun points straight ahead at the bottom centre of the screen. The SH-35 shotgun and MG-60
  machine gun are the shotgun and chaingun. Every Freedoom weapon frame gets the rest pose kicked back and up by a
  per-frame recoil amount (`RECOIL`), and the muzzle flashes (PISF, SHTF, CHGF, MISF, PLSF, BFGF) are drawn
  procedurally: yellow for guns, a fireball for rockets, cyan for plasma, green for the BFG.
- **Reloads and footsteps** (`extra_sounds.wad`, built with `build_sounds.py --peak 110`, which normalizes the quiet
  TGMC files): the shotgun pump (`DSSGCOCK`), the super shotgun's open, load and close (`DSDBOPN`, `DSDBLOAD`,
  `DSDBCLS`) and the weapon pickup (`DSWPNUP`) use TGMC gun-handling sounds. For GZDoom/UZDoom, the WAD also has a
  `TGMCMarine` player class (`marine_steps.decorate`) whose walking frames play a random TGMC floor footstep
  (`extra_sounds.sndinfo`), made the default class by `marine_steps.mapinfo`. Other engines ignore those lumps and
  still get the reload sounds. The same WAD has TGMC doors, blast doors, lifts, switches, the locked-door buzz,
  teleport, and the marine's pain, death and gib screams; in GZDoom, SNDINFO splits Doom's single pickup sound
  into a hypospray for health, armor clicks for armor, a magazine for ammo and a beep for keys.
- **Heavy guns and alien voices**: `heavy_gun_sounds.wad` gives the rocket launcher, plasma rifle, BFG, super
  shotgun, chainsaw (the power axe pickup) and fist TGMC sounds. Its SNDINFO gives the chaingun the MG-60's own fire
  sound (`gun_mg60.ogg`; other engines share Doom's pistol sound for both) and makes barrel and rocket explosions
  pick one of TGMC's medium explosions (`DSBAREXP` itself is one of them, for other engines). `build_sounds.py`
  accepts `NAME=file@seconds` to give one sound its own length. `alien_sounds.wad` gives every other monster
  caste-fitting TGMC roars, hisses, drools, claw and bite sounds and death screams (the Queen's screech, the King's
  roar for the Dragon, heavy alien footsteps for the Dragon and Queen), and the facehugger its leap and death sound.
- **Pickups and decorations** (`build_item_pickups.py`): besides armor and health, berserk = TGMC "bezerk" kit,
  soulsphere and megasphere = advanced and O2 first-aid kits, backpack = marine backpack, light amp = night-vision
  goggles, computer map = tablet, radiation suit = TGMC rad suit, invulnerability = bomb suit, invisibility = xeno
  costume, keys = the silver ID card tinted blue, red or yellow, shell/rocket boxes and cells = TGMC buckshot box,
  quad rockets, plasma cell and powerpack. The impaled-body and skull decorations (`POL1`-`POL6`) become xeno eggs,
  a burst egg and a resin pod.
- **Alien attacks** (`build_alien_attacks.py`, **GZDoom/UZDoom only**): the Spitter chaingunner, Queen (spiderdemon),
  Widow (arachnotron) and Dragon (cyberdemon) fire green acid instead of bullets, plasma and rockets, via DECORATE
  replacements; the cacodemon, mancubus and revenant projectiles are recoloured green. The Lost Soul is a facehugger that
  runs on the floor (no flying, no glow, 0.7 size) and leaps at the player, biting if it lands on them; the
  Carrier (Pain Elemental) spits them out and they drop to the floor. Every alien bleeds green
  acid (`BloodColor`); this script owns all the alien DECORATE replacements, so no two WADs replace the same class.
- **SOM energy weapons** (`build_som_variants.py`): each SOM look fires with its own TGMC laser or plasma sound
  through a custom bullet attack (`A_CustomBulletAttack` + `SNDINFO`), so the player's guns keep the normal sounds.
- **Sizes**: `build_sprites.py --scale` sizes the living sprite (the Runner is 0.85) and `--death-scale` the death
  frames (default 0.75 of the living sprite).

- **Fuel tanks** (`build_fuel_tank.py`, `fuel_tank.wad`): the explosive barrel (`BAR1`, `BEXPA/B`) is the SS13/TGMC
  red fuel tank (`objects.dmi` `weldtank`), glowing hot just before it blows, and the blast (`BEXPC-E`) is TGMC's
  explosion animation (`96x96.dmi` `explosion`), centred on the tank.
- **Music** (`build_music.py`, `music.wad`, **GZDoom/UZDoom only**): TGMC's repository has one real song, the
  lobby theme (`config/lobby_themes/DawsonChristian.ogg`), plus the RoboCop elevator tune and the round ambience
  loops. The lobby theme plays on the title, finale and text screens, the elevator tune on the intermission, and
  the levels rotate through the lobby theme and nine ambience loops. Each track is stored once (loudness-normalized
  with ffmpeg `loudnorm` to -22 LUFS for the lobby theme and -26 for the ambience, well under the sound effects,
  re-encoded as Vorbis), and an `SNDINFO` lump maps every Doom 1 and Doom 2 music name to a
  track with `$musicalias`.

- **Title, menus and texts** (`build_presentation.py`, `presentation.wad`, **GZDoom/UZDoom**): TGMC lobby art
  (`icons/misc/lobby_art`, 608x480, the same 4:3 shape as Doom's 320x200 screen) becomes the title screen
  (`som_doomguy`, TGMC's Doom-cover parody), the title-loop page and the intermission background; the main-menu
  logo is the TGMC eagle with "TGMC" lettering. A DEHACKED `[STRINGS]` block (not LANGUAGE: Freedoom sets these
  strings in its own DEHACKED, which outranks LANGUAGE) names the levels after TGMC maps and replaces pickup,
  death, monster, weapon, skill and quit texts. GameInfo `forcetextinmenus` makes the skill and episode menus use
  the text, and the intermission level-name graphics (`CWILVxx`, `WILVem`) are redrawn with Freedoom's own font
  glyphs (`graphics/text/fontchars`), because the intermission always prefers a graphic when one exists.
- **Hive textures** (`build_hive_textures.py`, `hive_textures.wad`, **GZDoom/UZDoom**): Freedoom's flesh walls
  (`SKIN*`, `SKSNAKE*`, `SKSPINE*`, `SKULWAL*`, `SK_LEFT/RIGHT`, `SLOPPY*`) become TGMC resin walls with weeds at the
  bottom, eggs or a resin pod in the skull and face textures, and the snake-skin floors (`SFLR6_*`, `SFLR7_*`) become
  weeds. Same sizes as Freedoom's, stored as full-colour PNGs in the `TX_START` namespace (the Doom palette has
  almost no purple or teal, so quantizing them turned the resin into flat navy and grey).
- **Marine voice and hive ambience** (**GZDoom/UZDoom**): the `TGMCMarine` class shouts a TGMC warcry now and then
  while firing and calls for a medic below 30 health (`marine_voice.wad`). `hive_ambience.zs`, an event handler
  registered by `hive_ambience.mapinfo`, plays a distant roar, vent crawling or a moving egg every 20 to 45 seconds
  (`hive_ambience.wad`).

- **Xeno gibs and acid puddles** (`build_xeno_gibs.py`, `xeno_gibs.wad`, **GZDoom/UZDoom**): each caste's TGMC gib
  animation (the body bursting into acid) becomes a sprite set `XG??` (frames A-E from the animation, F the remains,
  one shared box, the living sprite's scale), used by `XDeath` states in `build_alien_attacks.py` with a `GibHealth`
  per alien (bosses still run `A_BossDeath`). Doom's gib sound is TGMC's `gib.ogg`. The acid projectiles sometimes
  leave a bubbling puddle (`ACPD`, Effects `acid2`) that lies flat on the floor and burns for a few seconds with
  damage type `Acid`; every alien has `DamageFactor "Acid", 0`.
- **More decorations** (`build_item_pickups.py`): lamps become TGMC floodlights and a lantern, candles, candelabras
  and torches lit TGMC flares (red, green, blue), hanging bodies and gibs marines cocooned in resin (they keep the
  original top offset, so they still hang from the ceiling), the tech column a telecomms rack.
- **HUD face** (`build_hud_face.py`, `hud_face.wad`): the status bar face is the composited marine's head and
  shoulders (13x13 TGMC pixels, scaled 2x), with blood per pain level, side views for turning, and tinted
  ouch, grin, rampage, god and dead faces.
- **Help and story screens** (`build_presentation.py`): `HELP`/`HELP1` are a TGMC "field manual" of the pickups
  (read from the built pickup WADs, `--wads`) labelled in Freedoom's small font over darkened lobby art; the story
  screens between episodes (`E1TEXT`-`E4TEXT`, `C1TEXT`-`C6TEXT`) are TGMC briefings over a dark weed floor
  (`TGMCSTRY`, from `build_hive_textures.py`).

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
