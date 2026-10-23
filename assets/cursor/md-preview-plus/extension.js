// Preview / Markdown buttons in the editor title bar: switch the active .md tab between the
// built-in Markdown preview and the text editor in place (open the other kind, close this one). The
// built-in preview itself is patched (preview_patch.js): covered tabs stay alive, file#L79 links jump to
// the line, file.md#anchor links scroll to the anchor, and links go to openLink first, which opens a link
// to a source line as of a commit (file?v=<commit>#L<line>) where that line is now.
// client/ patches the Cursor app so that a covered tab does not flash when shown again.
const vscode = require('vscode');
const path = require('path');
const { setPatched } = require('./preview_patch');
const { locate, fileAt } = require('./line_map');

const PREVIEW = 'vscode.markdown.preview.editor';
// a file as of a commit, read-only: mpp-commit:<the file's path>?<commit>
const COMMIT_SCHEME = 'mpp-commit';

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

// A link to a source line as of a commit, [VHCA.cpp:5149](../src/hca/VHCA.cpp?v=6faa4de858#L5149), or to lines
// #L5149-L5160. The preview hands every link clicked in it to this command first (preview_patch.js): true means it
// opened the link, false leaves the link to the preview. It opens the file in the worktree at the lines where they
// are now; when they have been changed or deleted since, at the lines in their place, with a button that shows the
// file as of the commit, read-only (COMMIT_SCHEME); when the file is gone, the file as of the commit.
async function openLink(href, from) {
    const link = /^([^?#]+)\?v=([0-9a-f]{7,40})#L(\d+)(?:-L(\d+))?$/i.exec(href);
    if (!link) {
        return false;
    }
    const [, target, commit, a, b = a] = link;
    // resolved the way the preview resolves it: a path starting with / from the workspace folder
    const relative = decodeURIComponent(target);
    const base = relative.startsWith('/') ? vscode.workspace.getWorkspaceFolder(from)?.uri.fsPath : path.dirname(from.fsPath);
    if (!base) {
        return false;
    }
    const file = path.join(base, relative);
    const worktree = vscode.Uri.file(file);
    const asOf = sha => worktree.with({ scheme: COMMIT_SCHEME, query: sha });
    const first = Number(a), last = Number(b);
    const span = n => last > first ? n + '-' + (n + last - first) : String(n);
    const cited = path.basename(file) + ':' + span(first);
    const where = await locate(file, commit, first, last);
    if (!where) {
        await show(worktree, first, last);
        vscode.window.showWarningMessage('md-preview-plus: ' + path.basename(file) + ' is not in commit ' + commit
            + ' of its repository, so ' + cited + ' is opened in the file as it is now, where it may be other code.');
    } else if (where.gone) {
        await show(asOf(where.sha), first, last);
        vscode.window.showInformationMessage(cited + ' is not in the worktree as it was at ' + commit
            + ': this is the file as of that commit, read-only.');
    } else if (where.changed) {
        // the lines in their place are selected; with none, the cursor goes where they were
        const replaced = where.end >= where.start;
        await show(worktree, where.start, replaced ? where.end : where.start, replaced);
        const button = 'Show as of ' + commit;
        vscode.window.showInformationMessage(cited + (replaced
            ? ' changed after ' + commit + '; these are the lines that replaced ' + (last > first ? 'them' : 'it') + ' in the worktree.'
            : ' was deleted after ' + commit + '; the cursor is where it was in the worktree.'), button)
            .then(choice => choice === button && show(asOf(where.sha), first, last));
    } else {
        await show(worktree, where.start, where.end);
        if (where.start !== first) {
            vscode.window.setStatusBarMessage(cited + ' at ' + commit + ' is ' + (last > first ? 'lines ' : 'line ')
                + span(where.start) + ' now', 5000);
        }
    }
    return true;
}

// <uri> in a text editor in the active group, lines from..to selected; a single line gets the cursor at its start, as
// the preview's own #L<line> links do, unless <select> says otherwise
async function show(uri, from, to, select = to > from) {
    const doc = await vscode.workspace.openTextDocument(uri);
    const end = select ? doc.lineAt(Math.min(to, doc.lineCount) - 1).range.end : new vscode.Position(from - 1, 0);
    await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Active, selection: new vscode.Range(new vscode.Position(from - 1, 0), end) });
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
        vscode.commands.registerCommand('mdPreviewPlus.openLink', openLink),
        vscode.workspace.registerTextDocumentContentProvider(COMMIT_SCHEME, { provideTextDocumentContent: uri => fileAt(uri.fsPath, uri.query) }));
    // the link menu of the preview: preview.js puts the link and the selection into the menu's context
    for (const [command, key] of [['mdPreviewPlus.copySelection', 'mppSelection'],
        ['mdPreviewPlus.copyLinkAddress', 'mppHref'], ['mdPreviewPlus.copyLinkText', 'mppText']]) {
        context.subscriptions.push(vscode.commands.registerCommand(command,
            menu => menu && typeof menu[key] === 'string' && vscode.env.clipboard.writeText(menu[key])));
    }
}

module.exports = { activate };
