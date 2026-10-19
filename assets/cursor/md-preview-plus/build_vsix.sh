#!/bin/bash
# Package this folder as a VSIX and install it into the Cursor server on this host.
# Usage: bash build_vsix.sh               -- install into this host's Cursor server, then "Developer: Reload Window"
#        bash build_vsix.sh --styles      -- preview.css / preview.js changed only: copy them into the installed
#                                            extension; closing and reopening the preview tab shows them
#        bash build_vsix.sh --vsix <file> -- only write the package, e.g. for Extensions > Install from VSIX...
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
if [ "${1:-}" = "--styles" ]; then
    for d in "$HOME"/.cursor-server/extensions/pexiang.md-preview-plus-*/; do
        cp "$src/preview.css" "$src/preview.js" "$d" && echo "updated $d"
    done
    exit 0
fi
read -r name ver publisher < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["name"], d["version"], d["publisher"])' "$src/package.json")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/extension"
cp "$src/package.json" "$src/extension.js" "$src/preview_patch.js" "$src/preview.js" "$src/preview.css" "$tmp/extension/"
cat > "$tmp/[Content_Types].xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".css" ContentType="text/css"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
XML
cat > "$tmp/extension.vsixmanifest" <<XML
<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="$name" Version="$ver" Publisher="$publisher"/>
    <DisplayName>Markdown Preview Plus</DisplayName>
    <Description xml:space="preserve">Built-in Markdown preview: heading sidebar, centred text, Preview / Markdown buttons.</Description>
    <Categories>Other</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.70.0" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
XML
vsix="$tmp/$name-$ver.vsix"
(cd "$tmp" && python3 -c 'import sys,zipfile
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    for f in sys.argv[2:]: z.write(f)' "$vsix" "[Content_Types].xml" extension.vsixmanifest extension/package.json extension/extension.js extension/preview_patch.js extension/preview.js extension/preview.css)
if [ "${1:-}" = "--vsix" ]; then
    cp "$vsix" "${2:?--vsix needs an output file}" && echo "wrote ${2}"
    exit 0
fi
server="$(ls -td "$HOME"/.cursor-server/bin/linux-x64/*/ | head -1)bin/cursor-server"
"$server" --install-extension "$vsix" --force
