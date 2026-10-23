#!/bin/bash
# Package this folder as a VSIX, with client/ inside it, and install it into the Cursor server on this host.
# The installed preview.css then links to the one here, and the server's remote settings to ../remote.settings.json,
# so an edit on either side is an edit to the file in this repository.
# Usage: bash build_vsix.sh               -- install into this host's Cursor server, then "Developer: Reload Window"
#        bash build_vsix.sh --styles      -- preview.js changed only: copy it into the installed extension; closing
#                                            and reopening the preview tab shows it (preview.css needs nothing)
#        bash build_vsix.sh --vsix <file> -- only write the package, e.g. for Extensions > Install from VSIX...
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
server="$HOME/.cursor-server"
if [ "${1:-}" = "--styles" ]; then
    for d in "$server"/extensions/*.md-preview-plus-[0-9]*/; do
        cp "$src/preview.js" "$d" && echo "updated $d"
    done
    exit 0
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# fields <package.json>: name, version, publisher, extension kind, display name, description, tab separated
fields() {
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("\t".join([d["name"], d["version"], d["publisher"], d["extensionKind"][0], d["displayName"], d["description"]]))' "$1"
}

# stage <folder> <to> <file>...: copy the files given, relative to <folder>, into <to>/extension
stage() {
    local dir=$1 to=$2 f
    shift 2
    for f in "$@"; do
        mkdir -p "$(dirname "$to/extension/$f")"
        cp "$dir/$f" "$to/extension/$f"
    done
}

# vsix <to> <file>: package what stage put into <to>
vsix() {
    local to=$1 out=$2 name ver publisher kind display description
    IFS=$'\t' read -r name ver publisher kind display description < <(fields "$to/extension/package.json")
    cat > "$to/[Content_Types].xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".css" ContentType="text/css"/>
  <Default Extension=".vsix" ContentType="application/zip"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
XML
    cat > "$to/extension.vsixmanifest" <<XML
<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="$name" Version="$ver" Publisher="$publisher"/>
    <DisplayName>$display</DisplayName>
    <Description xml:space="preserve">$description</Description>
    <Categories>Other</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.70.0" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="$kind" />
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
XML
    python3 -c 'import os,sys,zipfile
out, root = sys.argv[1:]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for d, _, files in os.walk(root):
        for f in files:
            z.write(os.path.join(d, f), os.path.relpath(os.path.join(d, f), root))' "$out" "$to"
}

stage "$src/client" "$work/client" package.json extension.js webview_patch.js
vsix "$work/client" "$work/client.vsix"
stage "$src" "$work/plus" package.json extension.js preview_patch.js line_map.js preview.js preview.css client/package.json
cp "$work/client.vsix" "$work/plus/extension/client.vsix"
vsix "$work/plus" "$work/plus.vsix"
if [ "${1:-}" = "--vsix" ]; then
    cp "$work/plus.vsix" "${2:?--vsix needs an output file}" && echo "wrote ${2}"
    exit 0
fi
"$(ls -td "$server"/bin/linux-x64/*/ | head -1)bin/cursor-server" --install-extension "$work/plus.vsix" --force

IFS=$'\t' read -r name ver publisher _ < <(fields "$src/package.json")
installed="$server/extensions/${publisher,,}.$name-$ver"   # the extension id in lower case
ln -sfn "$src/preview.css" "$installed/preview.css"
settings="$server/data/Machine/settings.json"
repo_settings="$(cd "$src/.." && pwd)/remote.settings.json"
if [ ! -L "$settings" ]; then
    if [ -e "$settings" ] && ! cmp -s "$settings" "$repo_settings"; then
        echo "$settings differs from $repo_settings: merge them by hand, then run this again" >&2
        exit 1
    fi
    mkdir -p "$(dirname "$settings")"
    ln -sfn "$repo_settings" "$settings"
fi
echo "linked $installed/preview.css and $settings to this repository"
