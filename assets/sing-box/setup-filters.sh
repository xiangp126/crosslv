#!/bin/bash
# Register this repository's git content filters. Run ONCE PER CLONE.
#
# Why this is needed at all
# -------------------------
# Filter definitions live in .git/config, which is NOT part of the repository, so a fresh
# clone has none of them. Meanwhile .gitattributes still says `filter=secrets`, and when a
# filter is referenced but undefined git passes the content through **unfiltered and without
# an error** — real secrets land in the commit silently.
#
# That is not hypothetical: the secrets filter in this repo sat unregistered for months.
# `clean.sh` was correct the whole time and was simply never called.
#
# Usage
#   bash assets/sing-box/setup-filters.sh           configure (idempotent, safe to re-run)
#   bash assets/sing-box/setup-filters.sh --check    report status only, change nothing
#
# Re-run the configure mode whenever a filter definition changes (script moved, filter added).
set -u

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not inside a git repo" >&2; exit 1; }

RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[93m'; BOLD='\033[1m'; GREY='\033[90m'; R='\033[0m'
ok()   { printf "  ${GREEN}OK${R}    %s\n" "$1"; }
bad()  { printf "  ${RED}MISS${R}  %s\n" "$1"; }
warn() { printf "  ${YELLOW}WARN${R}  %s\n" "$1"; }
note() { printf "  ${GREY}%s${R}\n" "$1"; }

# filter-name <TAB> attribute <TAB> command        (attribute: clean | smudge | required)
FILTERS='
secrets	clean	./assets/sing-box/clean.sh %f
secrets	smudge	./assets/sing-box/smudge.sh %f
secrets	required	true
codexcfg	clean	python3 assets/codex/strip-projects.py
codexcfg	required	true
'

# scripts the filters depend on — a moved/renamed script is the classic silent breakage
SCRIPTS='assets/sing-box/clean.sh assets/sing-box/smudge.sh assets/codex/strip-projects.py'

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

printf "${BOLD}git content filters — %s${R}\n" "$([ $CHECK = 1 ] && echo 'status' || echo 'configure')"

fail=0
printf "\n${BOLD}filters${R}\n"
while IFS=$'\t' read -r name attr cmd; do
    [ -z "$name" ] && continue
    cur=$(git config --get "filter.$name.$attr" || true)
    if [ "$cur" = "$cmd" ]; then
        ok "filter.$name.$attr"
    elif [ $CHECK = 1 ]; then
        if [ -z "$cur" ]; then bad "filter.$name.$attr  (not set)"; else warn "filter.$name.$attr = $cur  (expected: $cmd)"; fi
        fail=1
    else
        git config "filter.$name.$attr" "$cmd"
        ok "filter.$name.$attr  -> set"
    fi
done <<< "$FILTERS"

printf "\n${BOLD}scripts the filters call${R}\n"
for s in $SCRIPTS; do
    if [ -x "$s" ]; then ok "$s"
    elif [ -f "$s" ]; then warn "$s  (exists but not executable)"
    else bad "$s  (MISSING — filters will fail)"; fail=1
    fi
done

printf "\n${BOLD}.gitattributes entries${R}\n"
while read -r path filt; do
    [ -z "$path" ] && continue
    if git check-attr filter -- "$path" 2>/dev/null | grep -q ": filter: $filt$"; then
        ok "$path -> $filt"
    else
        bad "$path is not mapped to $filt"; fail=1
    fi
done <<'ATTRS'
assets/xray/sing-box-config.jsonc secrets
assets/wireguard/sing-box-config.jsonc secrets
assets/codex/config.toml codexcfg
ATTRS

echo
if [ $fail = 0 ]; then
    printf "${GREEN}${BOLD}all good${R}\n"
    [ $CHECK = 1 ] || note "filters are per-clone; re-run this after cloning elsewhere."
else
    if [ $CHECK = 1 ]; then
        printf "${RED}${BOLD}not fully configured${R} — run without --check to fix\n"
    else
        printf "${RED}${BOLD}something is still wrong${R} — see MISS/WARN above\n"
    fi
    exit 1
fi

# With required=true a broken filter aborts the operation instead of writing the raw file.
[ $CHECK = 1 ] || note "required=true is set: a failing filter now aborts git instead of passing content through."
