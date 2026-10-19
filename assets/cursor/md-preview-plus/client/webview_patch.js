// Patch to the Cursor app on the computer you sit at (not the server): a webview kept while hidden, such
// as a Markdown preview tab, no longer flashes when its tab is shown again after another tab in its group
// covered it. A webview sits in a layer over the editor, placed with CSS anchor positioning. While the
// tab is covered its editor is out of the DOM, so the hidden iframe falls back to 300x150; shown again,
// it lays the page out at 300px, paints that, then lays it out at full size. The patch keeps the size in
// px while the tab is hidden (release()) and puts the anchor styles back before showing it (_show()).
// VS Code 1.142 has the same code. product.json holds the file's sha256 (base64, no padding); a stale one
// makes Cursor report a corrupt installation, so it is updated with it. By hand:
//   node webview_patch.js [--revert] [<app dir>]   (default /Applications/Cursor.app/Contents/Resources/app)
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const KEY = 'vs/workbench/workbench.desktop.main.js';

// OverlayWebview as minified in Cursor 3.24 and 3.25 (VS Code 1.128). Both sites or neither: a size kept
// in px and never handed back to the anchor would stop the webview following the editor.
const SITES = [
    {
        name: 'release() keeps the size',
        from: 'this._overlayLayout&&(' +
            'this._overlayLayout.content.style.visibility="hidden"),' +
            'this._options.retainContextWhenHidden?',
        to: 'this._overlayLayout&&(' +
            'this._options.retainContextWhenHidden&&' +
            'this._anchorState?.anchorElement.isConnected&&' +
            '(r=>{r.width>0&&r.height>0&&(' +
            'this._overlayLayout.content.style.width=r.width+"px",' +
            'this._overlayLayout.content.style.height=r.height+"px")})' +
            '(this._overlayLayout.content.getBoundingClientRect()),' +
            'this._overlayLayout.content.style.visibility="hidden"),' +
            'this._options.retainContextWhenHidden?',
    },
    {
        name: '_show() re-anchors first',
        from: 'this._overlayLayout&&(' +
            'this._overlayLayout.content.style.visibility="visible")',
        to: 'this._overlayLayout&&(' +
            'this._overlayLayout.reapplyLayoutStyles(),' +
            'this._overlayLayout.content.style.visibility="visible")',
    },
];

const count = (text, part) => text.split(part).length - 1;

function workbenchFile(app) {
    return path.join(app, 'out', KEY);
}

function write(file, text) {
    const tmp = file + '.patch-' + process.pid;
    fs.writeFileSync(tmp, text);
    fs.renameSync(tmp, file);
}

// on: true applies the patch, false takes it out. Returns the names of the sites changed now and of the
// sites this version does not have as expected; when there are any of those, nothing is changed.
function setPatched(app, on) {
    const file = workbenchFile(app);
    let js = fs.readFileSync(file, 'utf8');
    const changed = [], missing = [];
    for (const site of SITES) {
        const [now, want] = on ? [site.from, site.to] : [site.to, site.from];
        if (count(js, now) === 0 && count(js, want) === 1) {
            continue;
        }
        if (count(js, now) !== 1 || count(js, want) !== 0) {
            missing.push(site.name);
            continue;
        }
        js = js.replace(now, () => want);
        changed.push(site.name);
    }
    const productFile = path.join(app, 'product.json');
    const product = fs.readFileSync(productFile, 'utf8');
    const old = JSON.parse(product).checksums[KEY];
    if (count(product, `"${old}"`) !== 1) {
        missing.push('its checksum in product.json');
    }
    if (missing.length > 0) {
        return { changed: [], missing };
    }
    const sum = crypto.createHash('sha256').update(js).digest('base64').replace(/=+$/, '');
    if (changed.length > 0) {
        write(file, js);
    }
    if (sum !== old) {
        write(productFile, product.replace(`"${old}"`, () => `"${sum}"`));
    }
    return { changed, missing };
}

module.exports = { setPatched };

if (require.main === module) {
    const args = process.argv.slice(2);
    const revert = args[0] === '--revert';
    const app = args[revert ? 1 : 0] || '/Applications/Cursor.app/Contents/Resources/app';
    const { changed, missing } = setPatched(app, !revert);
    console.log('changed: ' + (changed.join('; ') || 'none'));
    if (missing.length > 0) {
        console.log('not found, so nothing changed: ' + missing.join('; '));
    }
    process.exit(missing.length > 0 ? 1 : 0);
}
