#!/bin/bash
# Replace Doom's bigger monsters with TGMC xeno castes.
#
# usage: build_aliens.sh TGMC_ROOT FREEDOOM_ROOT IWAD OUT_DIR
#   OUT_DIR is the same directory build_all.sh uses (needs tgmc_sprites/ inside); WADs go to OUT_DIR/wads.
#
# Each line of the table: Doom sprite prefix | TGMC caste (file) | walk state | dead state | wad name
# Rotating frames (walk, attack, pain) all use the caste's 4-direction walk art; the single-rotation
# frames (death, explosion) use the caste's "Dead" image at the living sprite's scale.
set -euo pipefail
if [ "$#" -ne 4 ]; then sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1; fi
TGMC=$(realpath "$1"); FD=$(realpath "$2"); IWAD=$(realpath "$3"); OUT=$(realpath "$4")
HERE=$(cd "$(dirname "$0")" && pwd)
PY="python3 -I"; TS="$OUT/tgmc_sprites"; WADS="$OUT/wads"; mkdir -p "$WADS"

(cd "$TGMC" && $PY "$HERE/extract_dmi.py" . "$TS" \
  icons/Xeno/castes/crusher.dmi icons/Xeno/castes/warrior.dmi icons/Xeno/castes/hunter.dmi \
  icons/Xeno/castes/boiler.dmi icons/Xeno/castes/widow.dmi icons/Xeno/castes/carrier.dmi \
  icons/Xeno/castes/dragon.dmi icons/Xeno/castes/queen.dmi icons/Xeno/castes/shrike.dmi \
  icons/Xeno/castes/larva.dmi icons/Xeno/castes/runner.dmi >/dev/null)

while IFS='|' read -r PRE CASTE WALK DEAD WAD; do
  case "$PRE" in ''|\#*) continue;; esac
  DIR="$TS/$CASTE"
  W=$(echo "$WALK" | tr ' ' '_')_f0_d; D="$DIR/$(echo "$DEAD" | tr ' ' '_')_f0_d0.png"
  $PY "$HERE/build_sprites.py" --prefix "$PRE" --auto-frames \
    --d0 "$DIR/${W}0.png" --d1 "$DIR/${W}1.png" --d2 "$DIR/${W}2.png" --d3 "$DIR/${W}3.png" \
    --death-png "$D" --freedoom "$FD/sprites" --buildcfg "$FD/buildcfg.txt" --playpal "$IWAD" \
    --out "$WADS/$WAD"
done <<'TABLE'
SARG|runner|Runner Walking|Runner Dead|alien_pinky.wad
SKUL|larva|Larva Moving|Larva Dead|alien_lostsoul.wad
HEAD|shrike|Shrike Walking|Shrike Dead|alien_cacodemon.wad
BOSS|crusher|Crusher Walking|Crusher Dead|alien_baron.wad
BOS2|warrior|Warrior Walking|Warrior Dead|alien_hellknight.wad
SKEL|hunter|Hunter Walking|Hunter Dead|alien_revenant.wad
FATT|boiler|Boiler Walking|Boiler Dead|alien_mancubus.wad
BSPI|widow|Widow Walking|Widow Dead|alien_arachnotron.wad
PAIN|carrier|Carrier Walking|Carrier Dead|alien_painelemental.wad
CYBR|dragon|Dragon Walking|Dragon Dead|alien_cyberdemon.wad
SPID|queen|Queen Walking|Queen Dead|alien_spiderdemon.wad
TABLE
echo "== alien enemy WADs in $WADS:"; ls -1 "$WADS" | grep '^alien_'
