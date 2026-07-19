#!/bin/bash
set -euo pipefail

REPO_DIR="${1:-$PWD}"
DEST="${CLANGD_HEADERS_DIR:-/auto/fwgwork1/$USER/clangd_headers}"
IMAGE_REPO="${IMAGE_REPO:-nbu-harbor.gtm.nvidia.com/hca-fw-core/hca-fw-core-ubuntu20.04}"
CDB="$REPO_DIR/compile_commands.json"

die() { echo "ERROR: $*" >&2; exit 1; }

[ -r "$CDB" ] || die "no compile_commands.json at $CDB (pass the repo dir as arg 1)"
mkdir -p "$DEST"

BUILD_DIR="$(grep -o '"directory": *"[^"]*"' "$CDB" | sed -n '1{s/.*: *"//; s/"$//; p}')"
[ -n "$BUILD_DIR" ] || die "no directory field in $CDB"
if [ "$(realpath -m "$BUILD_DIR/../../../../../../../../../clangd_headers")" != "$(realpath -m "$DEST")" ]; then
    die "utopx.clangd resolves headers as <build_dir>/../x9/clangd_headers which is not $DEST — repo not one level under the storage parent, or CDB layout changed; update the ../ count in utopx.clangd and here"
fi

mapfile -t CDB_PATHS < <(grep -o '/hcaFWCore[^" ]*' "$CDB" | sort -u)
[ "${#CDB_PATHS[@]}" -gt 0 ] || die "no /hcaFWCore paths in $CDB"

VERIX_PATH="" BOOST_PATH="" ASIO_PATH=""
UNKNOWN=()
for p in "${CDB_PATHS[@]}"; do
    case "$p" in
        /hcaFWCore/verix/*/include) VERIX_PATH="$p" ;;
        /hcaFWCore/boost/arm_agent/asio) ASIO_PATH="$p" ;;
        /hcaFWCore/boost/*/include) BOOST_PATH="$p" ;;
        *) UNKNOWN+=("$p") ;;
    esac
done
[ -n "$VERIX_PATH" ] || die "no verix include path in CDB"
[ -n "$BOOST_PATH" ] || die "no boost include path in CDB"
[ -n "$ASIO_PATH" ] || die "no asio include path in CDB"

VERIX_VER="$(basename "$(dirname "$VERIX_PATH")")"
BOOST_VER="$(basename "$(dirname "$BOOST_PATH")")"
WANT_VERIX="verix_${VERIX_VER}_include"
WANT_BOOST="boost_${BOOST_VER}_include"

NEED=()
[ -d "$DEST/$WANT_VERIX" ] || NEED+=(verix)
[ -d "$DEST/$WANT_BOOST" ] || NEED+=(boost)
if [ "${#NEED[@]}" -gt 0 ] || [ ! -e "$DEST/asio_current" ]; then
    NEED+=(asio)
fi

if [ "${#NEED[@]}" -gt 0 ]; then
    IMAGE="${IMAGE:-$(docker images --format '{{.Repository}}:{{.Tag}}' "$IMAGE_REPO" | sed -n 1p)}"
    [ -n "$IMAGE" ] || die "no local $IMAGE_REPO image; docker pull it first"
    TAG="${IMAGE##*:}"
    cid="$(docker create "$IMAGE")"
    trap 'docker rm "$cid" >/dev/null' EXIT

    fetch() {
        local src="$1" dst="$2" tmp="$DEST/.tmp.$$"
        rm -rf "$tmp"
        docker cp -q "$cid:$src" "$tmp" \
            || die "image $IMAGE lacks $src — CDB newer than local image? docker pull $IMAGE_REPO"
        rm -rf "$DEST/$dst"
        mv "$tmp" "$DEST/$dst"
        echo "$IMAGE $src" > "$DEST/.src_$dst"
        echo "extracted: $dst  <-  $IMAGE  $src"
    }

    for role in "${NEED[@]}"; do
        case "$role" in
            verix) fetch "$VERIX_PATH" "$WANT_VERIX" ;;
            boost) fetch "$BOOST_PATH" "$WANT_BOOST" ;;
            asio)  fetch "$ASIO_PATH" "asio_img${TAG}"
                   ln -sfn "asio_img${TAG}" "$DEST/asio_current" ;;
        esac
    done
fi

ln -sfn "$WANT_VERIX" "$DEST/verix_current"
ln -sfn "$WANT_BOOST" "$DEST/boost_current"

[ -f "$DEST/verix_current/VeriXDataBase.h" ] || die "verix_current broken (no VeriXDataBase.h)"
[ -d "$DEST/boost_current/xercesc" ] || die "boost_current broken (no bundled xercesc)"
[ -f "$DEST/asio_current/asio.hpp" ] || die "asio_current broken (no asio.hpp)"

if [ "${#UNKNOWN[@]}" -gt 0 ]; then
    echo "WARNING: unhandled /hcaFWCore paths in CDB — extend this script + utopx.clangd:"
    printf '  %s\n' "${UNKNOWN[@]}"
fi

echo "in sync with $CDB:"
echo "  storage: $DEST"
echo "  verix_current -> $(readlink "$DEST/verix_current")"
echo "  boost_current -> $(readlink "$DEST/boost_current")"
echo "  asio_current  -> $(readlink "$DEST/asio_current")"
if [ "${#NEED[@]}" -gt 0 ]; then
    echo "headers changed: restart clangd in the editor (clangd: Restart language server)"
fi
