#!/bin/bash
# Screenshots of a walkthrough page with headless Firefox and reduced motion (each step at its end state).
#   shots.sh PAGE.html OUTDIR WIDTH stage|card STEP_ID...
# stage: the page opened at a step (#go-<id>, header hidden) - the stage and the top of the step.
# card:  only that step's card.
# Writes OUTDIR/<mode>_<step id>_<width>.png and prints each file with its size.
set -u
if [ $# -lt 5 ]; then
    sed -n '2,6p' "$0"
    exit 2
fi
page=$1 out=$2 width=$3 mode=$4
shift 4
command -v firefox >/dev/null || { echo "firefox not found" >&2; exit 2; }
mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# open the step named in #go-<id> without scrolling, so the screenshot starts at the stage
sed -e "s/if (fromHash > 0) { go(fromHash, { instant: true }); }/if (fromHash > 0) { go(fromHash, { noScroll: true }); }/" \
    -e "s/'#' + m.id === location.hash/'#go-' + m.id === location.hash/" \
    -e 's#<style>#<style>.hero{display:none!important}#' "$page" > "$tmp/stage.html"
echo 'user_pref("ui.prefersReducedMotion", 1);' > "$tmp/user.js"
unset DISPLAY
for sid in "$@"; do
    src=$tmp/stage.html
    if [ "$mode" = card ]; then
        src=$tmp/card_$sid.html
        sed -e "s|<style>|<style>.stage-wrap,.transport,#summary,.howto,.gap,.flow-head,article.step:not(#$sid){display:none!important}|" \
            "$tmp/stage.html" > "$src"
    fi
    png=$out/${mode}_${sid}_${width}.png
    timeout 120 firefox --headless --no-remote --profile "$tmp" --window-size="$width,900" --screenshot "$png" \
        "file://$src#go-$sid" >/dev/null 2>&1
    if [ -s "$png" ]; then
        echo "$png $(stat -c %s "$png")"
    else
        echo "$png NOT WRITTEN" >&2
    fi
done
