// Runs in Cursor on the computer you sit at (extensionKind ui), where md-preview-plus installs it, and
// keeps webview_patch.js applied to that Cursor: an update or a reinstall brings an unpatched app.
// Cursor reads the checksums in product.json once, when it starts: after the patch it has to be quit and
// opened again. A window reload alone loads the patched code but reports a corrupt installation.
const vscode = require('vscode');
const { setPatched } = require('./webview_patch');

function activate(context) {
    // md-preview-plus asks for this to tell whether this extension is installed, and which version
    context.subscriptions.push(vscode.commands.registerCommand('mdPreviewPlusClient.version',
        () => context.extension.packageJSON.version));
    let result;
    try {
        result = setPatched(vscode.env.appRoot, true);
    } catch (e) {
        result = { changed: [], missing: ['all of it (' + e.message + ')'] };
    }
    if (result.missing.length > 0) {
        vscode.window.showWarningMessage('md-preview-plus-client: not found in this Cursor, so not patched: '
            + result.missing.join('; ') + ' (webview_patch.js).');
    } else if (result.changed.length > 0) {
        vscode.window.showInformationMessage('Cursor patched (md-preview-plus-client: covered previews keep their '
            + 'size); quit Cursor and open it again to apply.', 'Quit Cursor')
            .then(choice => choice && vscode.commands.executeCommand('workbench.action.quit'));
    }
}

module.exports = { activate };
