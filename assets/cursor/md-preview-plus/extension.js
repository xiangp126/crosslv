// Preview / Markdown buttons in the editor title bar: switch the active .md tab between the
// built-in Markdown preview and the text editor in place (open the other kind, close this one).
// Markdown preview tabs are also kept open, so links to other .md files open new tabs.
const vscode = require('vscode');

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

function activate(context) {
    context.subscriptions.push(
        vscode.commands.registerCommand('mdPreviewPlus.showPreview', () => switchActiveTab(true)),
        vscode.commands.registerCommand('mdPreviewPlus.showSource', () => switchActiveTab(false)),
        vscode.window.tabGroups.onDidChangeTabs(keepActivePreviewTab));
    keepActivePreviewTab();
}

module.exports = { activate };
