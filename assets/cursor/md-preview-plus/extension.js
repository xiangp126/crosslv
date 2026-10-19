// Preview / Markdown buttons in the editor title bar: switch the active .md tab between the
// built-in Markdown preview and the text editor in place (open the other kind, close this one).
// Markdown preview tabs are also kept open, so links to other .md files open new tabs. The built-in
// preview itself is patched (preview_patch.js): covered tabs stay alive, file#L79 links jump to the line.
// client/ patches the Cursor app so that a covered tab does not flash when shown again.
const vscode = require('vscode');
const path = require('path');
const { setPatched } = require('./preview_patch');

const PREVIEW = 'vscode.markdown.preview.editor';

function isPreview(input) {
    return input instanceof vscode.TabInputCustom && input.viewType === PREVIEW;
}

function isText(input) {
    return input instanceof vscode.TabInputText;
}

async function switchActiveTab(toPreview) {
    const group = vscode.window.tabGroups.activeTabGroup;
    const tab = group.activeTab;
    if (!tab || !tab.input || !tab.input.uri) {
        return;
    }
    const uri = tab.input.uri;
    const column = group.viewColumn;
    await vscode.commands.executeCommand('vscode.openWith', uri, toPreview ? PREVIEW : 'default', column);
    const now = vscode.window.tabGroups.all.find(g => g.viewColumn === column);
    if (!now) {
        return;
    }
    // the tab we came from; a text tab with unsaved edits stays open
    const leftovers = now.tabs.filter(t => t.input && t.input.uri && t.input.uri.toString() === uri.toString()
        && (toPreview ? isText(t.input) : isPreview(t.input)) && !t.isDirty);
    if (leftovers.length > 0) {
        await vscode.window.tabGroups.close(leftovers, true);
    }
}

// A link to another .md replaces a preview-mode (italic) tab instead of opening its own, so keep
// every Markdown preview tab the moment it becomes active.
function keepActivePreviewTab() {
    const tab = vscode.window.tabGroups.activeTabGroup.activeTab;
    if (tab && tab.isPreview && isPreview(tab.input)) {
        vscode.commands.executeCommand('workbench.action.keepEditor');
    }
}

// A Cursor update brings an unpatched built-in preview: patch it again. It takes effect when the preview
// extension next loads, so ask for a reload only if it is already running.
function patchBuiltinPreview() {
    const markdown = vscode.extensions.getExtension('vscode.markdown-language-features');
    if (!markdown) {
        return;
    }
    let result;
    try {
        result = setPatched(markdown.extensionPath, true);
    } catch (e) {
        result = { changed: [], missing: ['all of them (' + e.message + ')'] };
    }
    if (result.changed.length > 0 && markdown.isActive) {
        vscode.window.showInformationMessage('Markdown preview patched (' + result.changed.join('; ')
            + '); reload the window to apply.', 'Reload Window')
            .then(choice => choice && vscode.commands.executeCommand('workbench.action.reloadWindow'));
    }
    if (result.missing.length > 0) {
        vscode.window.showWarningMessage('md-preview-plus: not found in this Markdown preview, so not patched: '
            + result.missing.join('; ') + ' (preview_patch.js).');
    }
}

// client/ has to run in Cursor on the computer you sit at, which this extension does not reach from the
// remote: install it there (client.vsix, built by build_vsix.sh), and again when the one here is newer.
// It answers mdPreviewPlusClient.version; without it that command does not exist.
async function installClient(context) {
    const bundled = require('./client/package.json').version;
    const installed = await vscode.commands.executeCommand('mdPreviewPlusClient.version').then(v => v, () => '0');
    if (!isOlder(installed, bundled)) {
        return;
    }
    try {
        await vscode.commands.executeCommand('workbench.extensions.installExtension',
            vscode.Uri.file(path.join(context.extensionPath, 'client.vsix')));
        vscode.window.showInformationMessage('md-preview-plus: installed md-preview-plus-client ' + bundled
            + ' in Cursor on this computer.');
    } catch (e) {
        vscode.window.showWarningMessage('md-preview-plus: could not install md-preview-plus-client: ' + e.message);
    }
}

function isOlder(a, b) {
    const x = a.split('.').map(Number), y = b.split('.').map(Number);
    for (let i = 0; i < 3; i++) {
        if ((x[i] || 0) !== (y[i] || 0)) {
            return (x[i] || 0) < (y[i] || 0);
        }
    }
    return false;
}

function activate(context) {
    patchBuiltinPreview();
    installClient(context);
    context.subscriptions.push(
        vscode.commands.registerCommand('mdPreviewPlus.showPreview', () => switchActiveTab(true)),
        vscode.commands.registerCommand('mdPreviewPlus.showSource', () => switchActiveTab(false)),
        vscode.window.tabGroups.onDidChangeTabs(keepActivePreviewTab));
    keepActivePreviewTab();
}

module.exports = { activate };
