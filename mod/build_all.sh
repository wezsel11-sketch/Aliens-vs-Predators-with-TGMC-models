#!/bin/bash
# Rebuild every PWAD of the TGMC-in-Freedoom mod from source checkouts.
#
# usage: build_all.sh TGMC_ROOT FREEDOOM_ROOT IWAD OUT_DIR
#   TGMC_ROOT      checkout of tgstation/terragov-marine-corps
#   FREEDOOM_ROOT  checkout of freedoom/freedoom (sprites/ and buildcfg.txt are used)
#   IWAD           freedoom1.wad or freedoom2.wad (the palette is read from its PLAYPAL lump)
#   OUT_DIR        where extracted sprites and the built WADs go (not committed)
#
# Needs Python 3 with Pillow, and ffmpeg for the sound WADs.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi
TGMC=$(realpath "$1"); FD=$(realpath "$2"); IWAD=$(realpath "$3"); OUT=$(mkdir -p "$4" && realpath "$4")
HERE=$(cd "$(dirname "$0")" && pwd)
PY="python3 -I"
CFG="$FD/buildcfg.txt"; SPR="$FD/sprites"
TS="$OUT/tgmc_sprites"; WADS="$OUT/wads"; TMP="$OUT/tmp"
mkdir -p "$TS" "$WADS" "$TMP"

echo "== 1. extract TGMC sheets"
(cd "$TGMC" && $PY "$HERE/extract_dmi.py" . "$TS" \
  icons/Xeno/castes/runner.dmi icons/Xeno/castes/spitter.dmi \
  icons/mob/human_races/r_human.dmi \
  icons/mob/modular/som_armor.dmi icons/mob/modular/som_helmets.dmi \
  icons/mob/clothing/uniforms/marine_uniforms.dmi icons/mob/clothing/suits/marine_armor.dmi \
  icons/mob/clothing/headwear/marine_helmets.dmi \
  icons/obj/items/ammo/rifle.dmi icons/obj/items/ammo/packet.dmi icons/obj/items/ammo/rocket.dmi \
  icons/mob/inhands/weapons/ammo_left.dmi \
  icons/obj/items/guns/shotguns.dmi icons/obj/items/guns/shotguns64.dmi \
  icons/obj/items/guns/machineguns64.dmi icons/obj/items/guns/special64.dmi \
  icons/obj/items/guns/plasma64.dmi icons/obj/items/weapons/twohanded.dmi \
  icons/mob/clothing/uniforms/ert_uniforms.dmi icons/mob/clothing/feet.dmi icons/mob/clothing/hands.dmi \
  icons/mob/inhands/guns/rifles_right_1.dmi icons/mob/inhands/guns/shotguns_right_1.dmi \
  icons/mob/inhands/guns/machineguns_right_64.dmi icons/obj/items/guns/pistols.dmi)

# Item and decoration icons live in icons/obj/... (and icons/Xeno for eggs) and some share sheet names with the mob sheets above, so they get their own folder.
(cd "$TGMC" && $PY "$HERE/extract_dmi.py" . "$TS/obj_items" \
  icons/obj/clothing/suits/marine_armor.dmi icons/obj/clothing/headwear/marine_helmets.dmi \
  icons/obj/items/syringe.dmi icons/obj/stack_objects.dmi icons/obj/items/chemistry.dmi \
  icons/obj/items/storage/firstaid.dmi icons/obj/items/storage/backpack.dmi icons/obj/clothing/glasses.dmi \
  icons/obj/items/pda.dmi icons/obj/clothing/suits/suits.dmi icons/obj/items/card.dmi \
  icons/obj/items/ammo/box.dmi icons/obj/items/ammo/rocket.dmi icons/obj/items/ammo/energy.dmi \
  icons/obj/items/ammo/powerpack.dmi icons/Xeno/resin_pod.dmi icons/Xeno/Effects.dmi \
  icons/Xeno/structures.dmi icons/Xeno/weeds.dmi)

echo "== 2. composite humanoids (S, N, E, W per unit)"
# compose_units.py reads sheets from tgmc_sprites/ next to itself, so run it from a copy beside them.
cp "$HERE/compose_units.py" "$HERE/doomlib.py" "$OUT/"
$PY "$OUT/compose_units.py" "$OUT/marine_dirs" \
  x:marine_uniforms:marine_jumpsuit x:marine_armor:grenadier x:marine_helmets:helmet
# SOM: sleeved uniform, boots, gloves, black armor, helmet, and a held weapon (V-31 rifle / V-51 shotgun).
$PY "$OUT/compose_units.py" "$OUT/som_trooper_dirs" x:ert_uniforms:som_uniform x:feet:som x:hands:som \
  x:som_armor:som_medium_black x:som_helmets:som_helmet_black x:rifles_right_1:v31_w
$PY "$OUT/compose_units.py" "$OUT/som_heavy_dirs" x:ert_uniforms:som_uniform x:feet:som x:hands:som \
  x:som_armor:som_heavy_black x:som_helmets:som_helmet_black x:shotguns_right_1:v51_w
# The same units without the held weapon: they drop it when they fall.
$PY "$OUT/compose_units.py" "$OUT/som_trooper_dead_dirs" x:ert_uniforms:som_uniform x:feet:som x:hands:som \
  x:som_armor:som_medium_black x:som_helmets:som_helmet_black
$PY "$OUT/compose_units.py" "$OUT/som_heavy_dead_dirs" x:ert_uniforms:som_uniform x:feet:som x:hands:som \
  x:som_armor:som_heavy_black x:som_helmets:som_helmet_black

echo "== 3. actor sprite WADs"
build() { # prefix death-frames death-flag death-src dirs-prefix wad
  $PY "$HERE/build_sprites.py" --prefix "$1" --frames ABCD --attack-frames EFG \
    --d0 "$5"0.png --d1 "$5"1.png --d2 "$5"2.png --d3 "$5"3.png \
    --death-frames "$2" "$3" "$4" \
    --freedoom "$SPR" --buildcfg "$CFG" --playpal "$IWAD" --out "$WADS/$6"
}
# The imp slot is a Spitter too: it shoots fireballs, which are recolored green below.
build TROO IJKLMN --death-png "$TS/spitter/Spitter_Dead_f0_d0.png" "$TS/spitter/Spitter_Walking_f0_d" xeno_troo.wad
build PLAY NOPQRSTUVW --death-tilt-src "$OUT/marine_dirs/d0.png" "$OUT/marine_dirs/d" marine_player.wad
build POSS HIJKLMN --death-tilt-src "$OUT/som_trooper_dead_dirs/d0.png" "$OUT/som_trooper_dirs/d" som_trooper.wad
build SPOS HIJKLMN --death-tilt-src "$OUT/som_heavy_dead_dirs/d0.png" "$OUT/som_heavy_dirs/d" som_heavy.wad
build CPOS HIJKLMNOPQRST --death-png "$TS/spitter/Spitter_Dead_f0_d0.png" "$TS/spitter/Spitter_Walking_f0_d" spitter_chaingunner.wad

$PY "$HERE/build_recolor.py" --freedoom "$SPR" --buildcfg "$CFG" --playpal "$IWAD" --prefix BAL1 \
  --out "$WADS/green_fireball.wad"

echo "== 4. pickups (ammo, weapons, armor, medical)"
$PY "$HERE/build_ammo_pwad.py" --sprites "$TS" --freedoom "$SPR" --playpal "$IWAD" --out "$WADS/ammo_pickups.wad"
$PY "$HERE/build_weapon_pickups.py" --sprites "$TS" --freedoom "$SPR" --buildcfg "$CFG" \
  --playpal "$IWAD" --out "$WADS/weapon_pickups.wad"

$PY "$HERE/build_item_pickups.py" --sprites "$TS/obj_items" --freedoom "$SPR" --buildcfg "$CFG" \
  --playpal "$IWAD" --out "$WADS/item_pickups.wad"

echo "== 4b. optional voxel first-person weapons, and the rest of the alien enemies"
# Not loaded by default: Freedoom's own first-person guns are kept. Load weapon_view_voxel.wad to swap them.
PYTHONPATH="$HERE" python3 -s "$HERE/build_weapon_view.py" --sprites "$TS" --freedoom "$SPR" --buildcfg "$CFG" --playpal "$IWAD" \
  --out "$WADS/weapon_view_voxel.wad"
bash "$HERE/build_aliens.sh" "$TGMC" "$FD" "$IWAD" "$OUT"

echo "== 4c. five SOM looks per slot with a random spawner (GZDoom/UZDoom only)"
$PY "$HERE/build_som_variants.py" --out "$OUT" --freedoom "$FD" --iwad "$IWAD" --tgmc "$TGMC"

echo "== 4d. alien acid attacks and recolored projectiles (GZDoom/UZDoom only)"
$PY "$HERE/build_alien_attacks.py" --out "$OUT" --freedoom "$FD" --iwad "$IWAD"

echo "== 5. sounds"
V="$TGMC/sound/voice"; G="$TGMC/sound/weapons/guns/fire"
$PY "$HERE/build_sounds.py" --max-seconds 1.0 --out "$WADS/gun_sounds.wad" \
  --map DSPISTOL="$G/pistol.ogg" DSSHOTGN="$G/shotgun.ogg"
# sound_slots.deh points the chaingunner/imp at the alien sound slots (DEHACKED lump).
$PY "$HERE/build_sounds.py" --max-seconds 1.2 --out "$WADS/voice_sounds.wad" --raw DEHACKED="$HERE/sound_slots.deh" --map \
  DSPOSIT1="$V/human/male/warcry_1.ogg" DSPOSIT2="$V/human/male/warcry_2.ogg" DSPOSIT3="$V/human/male/warcry_3.ogg" \
  DSPOPAIN="$V/human/male/pain_1.ogg" \
  DSPODTH1="$V/human/male/scream_1.ogg" DSPODTH2="$V/human/male/scream_2.ogg" DSPODTH3="$V/human/male/scream_3.ogg" \
  DSBGSIT1="$V/alien/hiss1.ogg" DSBGSIT2="$V/alien/hiss2.ogg" DSBGACT="$V/alien/growl1.ogg" \
  DSBGDTH1="$V/alien/death.ogg" DSBGDTH2="$V/alien/death2.ogg" \
  DSCLAW="$V/alien/pounce.ogg" DSFIRSHT="$V/alien/spitacid.ogg" DSDMPAIN="$V/alien/growl2.ogg"

# Reloads, doors, lifts, switches, marine pain and pickup sounds replace Doom's slots; the marine player class
# adds TGMC footsteps and SNDINFO splits the pickup sound by item type (GZDoom/UZDoom only).
I="$TGMC/sound/weapons/guns/interact"; F="$TGMC/sound/effects/footstep"; M="$TGMC/sound/machines"; H="$V/human/male"
$PY "$HERE/build_sounds.py" --max-seconds 1.0 --peak 110 --out "$WADS/extra_sounds.wad" --map \
  DSSGCOCK="$I/shotgun_pump.ogg" DSDBOPN="$I/shotgun_open.ogg" DSDBLOAD="$I/shotgun_db_insert.ogg" \
  DSDBCLS="$I/martini_cocked.ogg" DSWPNUP="$I/cocked.ogg" \
  DSSTEP1="$F/floor1.ogg" DSSTEP2="$F/floor2.ogg" DSSTEP3="$F/floor3.ogg" DSSTEP4="$F/floor4.ogg" DSSTEP5="$F/floor5.ogg" \
  DSDOROPN="$M/door_open.ogg" DSDORCLS="$M/door_close.ogg" DSBDOPN="$M/blastdoor.ogg" DSBDCLS="$M/blastdoor.ogg" \
  DSSWTCHN="$M/switch.ogg" DSSWTCHX="$M/terminal_button01.ogg" DSPSTART="$M/elevator_move.ogg" \
  DSSTNMOV="$M/elevator_move.ogg" DSPSTOP="$M/elevator_openclose.ogg" DSNOWAY="$M/door_locked.ogg" \
  DSTELEPT="$TGMC/sound/effects/phasein.ogg" \
  DSPLPAIN="$H/pain_4.ogg" DSPLDETH="$H/scream_5.ogg" DSPDIEHI="$H/gored_1.ogg" DSOOF="$H/gasp1.ogg" \
  DSHYPO="$TGMC/sound/items/hypospray.ogg" DSARMPK="$TGMC/sound/items/armorlock.ogg" DSAMMPK="$I/m41a_reload.ogg" \
  DSKEYPK="$M/twobeep.ogg" DSGETPOW="$M/beepalert.ogg" \
  --raw DECORATE="$HERE/marine_steps.decorate" SNDINFO="$HERE/extra_sounds.sndinfo" MAPINFO="$HERE/marine_steps.mapinfo"
# The rocket launcher, plasma rifle, BFG, super shotgun, chainsaw (power axe) and fist.
W="$TGMC/sound/weapons"
$PY "$HERE/build_sounds.py" --max-seconds 1.5 --peak 115 --out "$WADS/heavy_gun_sounds.wad" --map \
  DSRLAUNC="$G/rpg_1.ogg" DSPLASMA="$G/plasma_fire_fast.ogg" DSBFG="$G/tank_bfg.ogg" DSDSHTGN="$G/shotgun_heavy.ogg" \
  DSSAWUP="$W/chainsawstart.ogg" DSSAWIDL="$W/chainsaw_simpson.ogg" DSSAWFUL="$W/chainsawhit.ogg" \
  DSSAWHIT="$W/chainsawhit.ogg" DSPUNCH="$W/punch1.ogg"
# Every other monster's voice: each caste gets TGMC roars, hisses and death screams.
A="$V/alien"; E="$TGMC/sound/effects/alien"
$PY "$HERE/build_sounds.py" --max-seconds 2.0 --peak 115 --out "$WADS/alien_sounds.wad" --map \
  DSSGTSIT="$A/roar1.ogg" DSSGTATK="$W/alien_bite1.ogg" DSSGTDTH="$A/death2.ogg" DSDMACT="$A/growl3.ogg" \
  DSCACSIT="$A/roar5.ogg" DSCACDTH="$A/death.ogg" DSBRSSIT="$A/roar9.ogg" DSBRSDTH="$A/death2.ogg" \
  DSKNTSIT="$A/roar3.ogg" DSKNTDTH="$A/death.ogg" \
  DSSKESIT="$A/hiss3.ogg" DSSKEACT="$A/drool1.ogg" DSSKEDTH="$A/death2.ogg" DSSKESWG="$E/tail_swipe1.ogg" \
  DSSKEPCH="$W/alien_claw_flesh1.ogg" DSSKEATK="$A/spitacid2.ogg" \
  DSMANSIT="$A/roar11.ogg" DSMANATK="$A/spitacid2.ogg" DSMNPAIN="$A/growl4.ogg" DSMANDTH="$A/death.ogg" \
  DSBSPSIT="$A/hiss2.ogg" DSBSPACT="$A/drool2.ogg" DSBSPDTH="$A/death2.ogg" DSBSPWLK="$E/footstep_medium1.ogg" \
  DSPESIT="$A/roar7.ogg" DSPEPAIN="$A/growl4.ogg" DSPEDTH="$A/death.ogg" \
  DSCYBSIT="$A/king_roar.ogg" DSCYBDTH="$A/king_died.ogg" DSHOOF="$E/footstep_large1.ogg" DSMETAL="$E/footstep_large2.ogg" \
  DSSPISIT="$A/queen_screech.ogg" DSSPIDTH="$A/queen_died.ogg" \
  DSVILSIT="$A/roar12.ogg" DSVILACT="$A/hiss1.ogg" DSVIPAIN="$A/growl1.ogg" DSVILDTH="$A/death2.ogg" \
  DSVILATK="$A/spitacid2.ogg" DSFLAMST="$A/spitacid.ogg" DSFLAME="$TGMC/sound/bullets/acid_impact1.ogg" \
  DSSKLATK="$A/pounce.ogg" DSHUGDTH="$A/facehugger_dies.ogg" --raw SNDINFO="$HERE/alien_sounds.sndinfo"

# Marine voice lines (played by the TGMCMarine class) and the hive ambience (a ZScript event handler).
$PY "$HERE/build_sounds.py" --max-seconds 2.5 --peak 110 --out "$WADS/marine_voice.wad" --map \
  DSWCRY1="$H/warcry_5.ogg" DSWCRY2="$H/warcry_13.ogg" DSWCRY3="$H/warcry_17.ogg" DSWCRY4="$H/warcry_21.ogg" \
  DSWCRY5="$H/warcry_25.ogg" DSMEDIC1="$H/medic.ogg" DSMEDIC2="$H/medic2.ogg" --raw SNDINFO="$HERE/marine_voice.sndinfo"
$PY "$HERE/build_sounds.py" --max-seconds 5.0 --peak 110 --out "$WADS/hive_ambience.wad" --map \
  DSHIVE1="$A/distantroar_3.ogg" DSHIVE2="$A/xenos_roaring.ogg" DSHIVE3="$A/4_xeno_roars.ogg" DSHIVE4="$A/roar10.ogg" \
  DSHIVE5="$E/ventcrawl1.ogg" DSHIVE6="$E/ventcrawl2.ogg" DSHIVE7="$E/ventpass1.ogg" DSHIVE8="$E/egg_move.ogg" \
  --raw ZSCRIPT="$HERE/hive_ambience.zs" SNDINFO="$HERE/hive_ambience.sndinfo" MAPINFO="$HERE/hive_ambience.mapinfo"

echo "== 6. music (GZDoom/UZDoom only)"
$PY "$HERE/build_music.py" --tgmc "$TGMC" --out "$WADS/music.wad"

echo "== 7. title screens, menu logo, texts and hive textures (GZDoom/UZDoom only)"
$PY "$HERE/build_presentation.py" --tgmc "$TGMC" --freedoom "$FD" --playpal "$IWAD" --out "$WADS/presentation.wad"
$PY "$HERE/build_hive_textures.py" --sprites "$TS/obj_items" --out "$WADS/hive_textures.wad"

echo "== done: WADs in $WADS"
ls -1 "$WADS"
