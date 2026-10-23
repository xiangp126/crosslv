// Patches to the built-in Markdown preview, made in place in its dist/extension.js. A Cursor update
// brings a fresh copy, so extension.js applies them on every start. By hand:
//   node preview_patch.js [--revert] <markdown-language-features dir>
'use strict';
const fs = require('fs');
const path = require('path');

// Each site: a pattern found exactly once in dist/extension.js, and the text inserted right after it.
const SITES = [
    // The preview creates its webviews without retainContextWhenHidden, so a covered tab is destroyed
    // and rebuilt from scratch when shown again. Keep the tab .md files open in (custom editor
    // vscode.markdown.preview.editor) ...
    {
        name: 'keep preview tabs',
        at: /registerCustomEditorProvider\([^)]*?webviewOptions:\{enableFindWidget:!0/g,
        add: () => ',retainContextWhenHidden:!0',
    },
    // ... and "Open Preview" panels.
    {
        name: 'keep Open Preview panels',
        at: /createWebviewPanel\([^;]*?\{enableFindWidget:!0/g,
        add: () => ',retainContextWhenHidden:!0',
    },
    // A change to the file while a kept tab is covered goes in place instead of reloading the page.
    {
        name: 'update covered tabs in place',
        at: /\|\|!this\._webviewPanel\.visible/g,
        add: () => '&&!this._webviewPanel.options?.retainContextWhenHidden',
    },
    // A link to file#L79 opens the file at line 79: the language server returns the line as
    // positionOrRange, this client reads position (upstream reads positionOrRange).
    {
        name: 'links to #L<line> jump to the line',
        at: /let (\w+)=await this\._client\.resolveLinkTarget\(\w+,\w+\);/g,
        add: m => `${m[1]}&&(${m[1]}.position??=${m[1]}.positionOrRange?.start??${m[1]}.positionOrRange);`,
    },
    // A link clicked in a preview goes to md-preview-plus first (command mdPreviewPlus.openLink in
    // extension.js, given the link as written and the preview's file), which opens a link to a source line
    // as of a commit, file?v=<commit>#L<line>, where that line is now. True means it opened the link; false,
    // an error, or md-preview-plus not running leaves the link to the preview as before.
    {
        name: 'preview links go to md-preview-plus first',
        at: /async _onDidClickPreviewLink\((\w+)\)\{/g,
        add: m => `if(await require("vscode").commands.executeCommand("mdPreviewPlus.openLink",${m[1]},this.resource).then(h=>h===!0,()=>!1))return;`,
    },
    // A link to file.md#anchor (a heading or an <a id>) opens that file's preview tab where it was last
    // left: the language server resolves the anchor to a line, the code that opens links hands the line to
    // vscode.open as a text selection, and a preview tab ignores the selection. The preview manager's line
    // monitor is what scrolls previews to a line when the editor scrolls; give it to the code that opens
    // links ...
    {
        name: 'link opener reaches the previews',
        at: /this\._topmostLineMonitor=new \w+;/g,
        add: () => 'this._opener._topmostLineMonitor=this._topmostLineMonitor;',
    },
    // ... so that a preview tab the link opens starts at the anchor's line (position, which the #L<line>
    // patch fills in) ...
    {
        name: 'links to file#anchor open a new preview there',
        at: /if\(!(\w+)\)return;let (\w+)=\w+\.Uri\.from\(\1\.uri\);/g,
        add: m => `${m[1]}.position&&this._topmostLineMonitor?.setPreviousStaticEditorLine({uri:${m[2]},line:${m[1]}.position.line});`,
    },
    // ... and one already open scrolls there, in place, once vscode.open has shown it.
    {
        name: 'links to file#anchor scroll an open preview',
        at: /return (\w+)\.commands\.executeCommand\("vscode\.open",(\w+),\{selection:(\w+)\.position\?[^;]*?\}\)/g,
        add: m => `.then(()=>${m[3]}.position&&this._topmostLineMonitor?.updateLine(${m[2]},${m[3]}.position.line))`,
    },
];

// on: true applies the patches, false takes them out. Returns the names of the sites changed now and
// of the sites this version does not have exactly once, which are left alone.
function setPatched(dir, on) {
    const file = path.join(dir, 'dist', 'extension.js');
    let js = fs.readFileSync(file, 'utf8');
    const edits = [], missing = [], changed = [];
    for (const site of SITES) {
        const found = [...js.matchAll(site.at)];
        if (found.length !== 1) {
            missing.push(site.name);
            continue;
        }
        edits.push({ name: site.name, end: found[0].index + found[0][0].length, add: site.add(found[0]) });
    }
    // from the end of the file back, so the earlier offsets stay valid
    for (const { name, end, add } of edits.sort((a, b) => b.end - a.end)) {
        const has = js.startsWith(add, end);
        if (on && !has) {
            js = js.slice(0, end) + add + js.slice(end);
        } else if (!on && has) {
            js = js.slice(0, end) + js.slice(end + add.length);
        } else {
            continue;
        }
        changed.push(name);
    }
    if (changed.length > 0) {
        const tmp = file + '.patch-' + process.pid;
        fs.writeFileSync(tmp, js);
        fs.renameSync(tmp, file);
    }
    return { changed, missing };
}

module.exports = { setPatched };

if (require.main === module) {
    const args = process.argv.slice(2);
    const revert = args[0] === '--revert';
    const dir = args[revert ? 1 : 0];
    if (!dir) {
        console.error('usage: node preview_patch.js [--revert] <markdown-language-features dir>');
        process.exit(2);
    }
    const { changed, missing } = setPatched(dir, !revert);
    console.log('changed: ' + (changed.join('; ') || 'none'));
    if (missing.length > 0) {
        console.log('not found: ' + missing.join('; '));
    }
    process.exit(missing.length > 0 ? 1 : 0);
}
