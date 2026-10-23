// Acceptance checks 1-7 and 13-16 of plans/md-preview-plus.md §7.3, in the Cursor that start.sh started, with the preview
// of long.md from make_sample.py as the active tab. Prints PASS or FAIL per check; exits 1 if any failed.
// On Linux the keys are Ctrl+F and Ctrl+Shift+V; the Cmd of Cmd+double-click is Meta.
//   node accept.mjs
import { connect, workbench, sleep, ev, click, prepare, preview } from './cdp.mjs';
import fs from 'fs';

const c = await connect();
const s = await workbench(c);
await prepare(c, s);
const results = [];
const check = (n, name, pass, detail) => {
    results.push(pass);
    console.log(`${pass ? 'PASS' : 'FAIL'} ${n} ${name}: ${detail}`);
};
const page = `document.getElementById('active-frame').contentWindow`;
const group = `document.querySelector('.editor-group-container.active')`;
const tabs = () => ev(c, s, `[...${group}.querySelectorAll('.tab')].map(t => t.getAttribute('aria-label') || '')`);
const activeIndex = () => ev(c, s, `[...${group}.querySelectorAll('.tab')].indexOf(${group}.querySelector('.tab.active'))`);
// a preview kept while hidden keeps its size, so "showing" means visible, not just wide
const previewShown = () => ev(c, s, `[...document.querySelectorAll('iframe.webview')].some(f => f.getBoundingClientRect().width > 0 && getComputedStyle(f.parentElement).visibility !== 'hidden')`);
const textShown = () => ev(c, s, `[...${group}.querySelectorAll('.monaco-editor .view-lines')].some(e => e.getBoundingClientRect().width > 0)`);
const titleActions = () => ev(c, s, `[...${group}.querySelectorAll('.editor-actions .action-label')].map(e => (e.getAttribute('aria-label') || '').split('\\n')[0])`);
async function key(k, code, vk, modifiers = 0, text) {
    await c.send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, modifiers, text }, s);
    await c.send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk, modifiers }, s);
}
async function clickTab(index) {
    const r = await ev(c, s, `(() => { const r = ${group}.querySelectorAll('.tab')[${index}].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
    await click(c, s, ...r);
    await sleep(1500);
}
async function closeTab(index) {
    await ev(c, s, `${group}.querySelectorAll('.tab')[${index}].querySelector('.tab-actions .action-label').click(), 1`);
    await sleep(1000);
}
// right-click at <x> <y>: the labels of the context menu that opens
async function rightClick(x, y) {
    await c.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y }, s);
    for (const type of ['mousePressed', 'mouseReleased']) {
        await c.send('Input.dispatchMouseEvent', { type, x, y, button: 'right', clickCount: 1 }, s);
    }
    await sleep(800);
    return ev(c, s, `[...document.querySelectorAll('.context-view .monaco-menu .action-item .action-label')].map(e => (e.getAttribute('aria-label') || e.textContent).trim()).filter(Boolean)`);
}
async function pickMenu(label) {
    const r = await ev(c, s, `(() => { const e = [...document.querySelectorAll('.context-view .monaco-menu .action-item .action-label')].find(e => (e.getAttribute('aria-label') || e.textContent).trim() === ${JSON.stringify(label)}); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
    if (r) {
        await click(c, s, ...r);
        await sleep(800);
    }
    return Boolean(r);
}
// window coordinates of the middle of the element <expr> evaluates to in the preview page, scrolled into view first
// unless <scroll> is false
async function at(w, expr, scroll = true) {
    const f = await ev(c, s, `(() => { const r = [...document.querySelectorAll('iframe')].find(f => f.src.includes('${w.id}')).getBoundingClientRect(); return [r.x, r.y]; })()`);
    const e = await ev(c, w.sessionId, `(() => { const af = document.getElementById('active-frame'); const o = af.getBoundingClientRect(); const el = (${expr}); ${scroll ? "el.scrollIntoView({ block: 'center' });" : ''} const r = el.getBoundingClientRect(); return [o.x + r.x + Math.min(r.width / 2, 40), o.y + r.y + r.height / 2]; })()`);
    return [f[0] + e[0], f[1] + e[1]];
}
const LINK = 'a[href*="sample.cpp#L79"]';

// 1 the .md opened as the preview, in place (not a "Preview xxx.md" panel, not a source editor)
let w = await preview(c, LINK);
const home = await activeIndex();
const label = (await tabs())[home];
check(1, 'md opens as the preview', !!w && label.startsWith('long.md') && await previewShown() && !await textShown(), `active tab "${label}"`);
if (!w) {
    process.exit(1);
}

// 2 sidebar: click the entry of section 70, the heading comes to the top and the Back button shows; Go Back
// (Ctrl+Alt+- on Linux) returns to where the page was (the button stays while earlier jumps of this page are
// left to go back to); a click with Meta held (Cmd on the Mac) shows the Back button too, which returns; after one
// more click Ctrl+Alt+← (⌃⌥←, Go Back in Peter's keybindings.json) returns as well; the long heading of section 43 wraps
const entries = await ev(c, w.sessionId, `${page}.document.querySelectorAll('#mpp-sidebar a').length`);
const ENTRY70 = `[...${page}.document.querySelectorAll('#mpp-sidebar a')].find(a => a.textContent.includes('70. 第 70 节'))`;
const entry70 = await at(w, ENTRY70);
const scrollY = () => ev(c, w.sessionId, `Math.round(${page}.scrollY)`);
const backShown = () => ev(c, w.sessionId, `!${page}.document.getElementById('mpp-back').hidden`);
const y0 = await scrollY();
await click(c, s, ...entry70);
await sleep(1000);
// + 0 turns -0 (a heading a fraction of a pixel above the top) into 0: the protocol cannot return -0
const top = await ev(c, w.sessionId, `Math.round([...${page}.document.querySelectorAll('h2')].find(h => h.textContent.includes('70. 第 70 节')).getBoundingClientRect().top) + 0`);
const backAfterJump = await backShown();
await key('-', 'Minus', 189, 1 | 2);
await sleep(800);
const y1 = await scrollY();
const backAfterBack = await backShown();
const metaAt = await at(w, ENTRY70);
const y2 = await scrollY();
await click(c, s, ...metaAt, { modifiers: 4 });
await sleep(1000);
const backAfterMeta = await backShown();
await click(c, s, ...await at(w, `${page}.document.getElementById('mpp-back')`, false));
await sleep(800);
const y3 = await scrollY();
const altAt = await at(w, ENTRY70);
const y4 = await scrollY();
await click(c, s, ...altAt);
await sleep(1000);
const y5 = await scrollY();
await key('ArrowLeft', 'ArrowLeft', 37, 1 | 2);
await sleep(800);
const y6 = await scrollY();
const resize = await ev(c, w.sessionId, `!!${page}.document.getElementById('mpp-resize')`);
const wrap = await ev(c, w.sessionId, `(() => {
    const items = [...${page}.document.querySelectorAll('#mpp-sidebar a')];
    const range = ${page}.document.createRange();
    range.selectNodeContents(items.find(a => a.textContent.startsWith('43. ')));
    return { cut: items.filter(a => a.scrollWidth > a.clientWidth + 1).length,
             lines: new Set([...range.getClientRects()].map(r => Math.round(r.top))).size };
})()`);
check(2, 'sidebar and Back', entries > 80 && top >= 0 && top < 150 && backAfterJump && Math.abs(y1 - y0) <= 1
    && backAfterMeta && Math.abs(y3 - y2) <= 1 && Math.abs(y5 - y4) > 1 && Math.abs(y6 - y4) <= 1 && resize && wrap.lines > 1 && wrap.cut === 0,
    `${entries} entries; section 70 at ${top}px after the click, Back button ${backAfterJump ? 'shown' : 'missing'}; Go Back: scroll ${y0} → ${y1}, button ${backAfterBack ? 'still shown' : 'hidden'}; `
    + `Meta+click: Back button ${backAfterMeta ? 'shown' : 'missing'}, the button: scroll ${y2} → ${y3}; `
    + `click: scroll ${y4} → ${y5}, Ctrl+Alt+←: ${y6}; `
    + `drag bar ${resize ? 'present' : 'missing'}; the long heading on ${wrap.lines} line(s), ${wrap.cut} entries cut off`);

// 3 find: Ctrl+F, type, Enter moves to the next match, Esc closes
await click(c, s, ...await at(w, `${page}.document.querySelectorAll('.markdown-body p')[5]`));
await key('f', 'KeyF', 70, 2);
await sleep(300);
await c.send('Input.insertText', { text: 'VHCA' }, s);
await sleep(900);
const count = () => ev(c, w.sessionId, `(() => { const b = ${page}.document.getElementById('mpp-find'); return b && !b.hidden ? b.querySelector('span').innerText : 'closed'; })()`);
const first = await count();
await key('Enter', 'Enter', 13, 0, '\r');
await sleep(300);
const second = await count();
await key('Escape', 'Escape', 27);
await sleep(300);
const closed = await count();
const [a, n] = (first.match(/^(\d+) of (\d+)$/) || []).slice(1).map(Number);
check(3, 'find', n > 0 && second === `${a % n + 1} of ${n}` && closed === 'closed', `"${first}" → Enter "${second}" → Esc ${closed}`);

// 4 a link to another .md opens a new tab and leaves this one; right-click on a link, in the text or in the
// sidebar: Copy Link Address and Copy Link Text instead of Cut / Copy / Paste, which stay elsewhere; a sidebar
// entry's address is this file's path with the heading's #anchor
const before = await tabs();
await click(c, s, ...await at(w, `${page}.document.querySelector('a[href$="other.md"]')`));
await sleep(2000);
const after = await tabs();
const opened = after[await activeIndex()];
await closeTab(await activeIndex());
await clickTab(home);
w = await preview(c, LINK);
await c.send('Browser.grantPermissions', { origin: await ev(c, s, 'location.origin'), permissions: ['clipboardReadWrite', 'clipboardSanitizedWrite'] });
const source = await ev(c, w.sessionId, `JSON.parse(${page}.document.getElementById('vscode-markdown-preview-data').getAttribute('data-settings')).source`);
const want4 = decodeURIComponent(new URL('other.md', source).pathname);
// right-click the element <expr> evaluates to, pick Copy Link Address: the menu, and the clipboard after it
async function copyLinkAddress(expr) {
    const menu = await rightClick(...await at(w, expr));
    if (!await pickMenu('Copy Link Address')) {
        await key('Escape', 'Escape', 27);
        await sleep(300);
    }
    return [menu, await ev(c, s, `navigator.clipboard.readText()`)];
}
const [linkMenu, copied] = await copyLinkAddress(`${page}.document.querySelector('a[href$="other.md"]')`);
const ENTRY = `[...${page}.document.querySelectorAll('#mpp-sidebar a')].find(a => a.textContent.includes('70. 第 70 节'))`;
const entry = new URL(await ev(c, w.sessionId, `${ENTRY}.getAttribute('href')`), source);
const wantEntry = decodeURIComponent(entry.pathname + entry.hash);
const [entryMenu, entryCopied] = await copyLinkAddress(ENTRY);
const textMenu = await rightClick(...await at(w, `${page}.document.querySelectorAll('.markdown-body p')[5]`));
await key('Escape', 'Escape', 27);
await sleep(300);
check(4, 'md link opens a new tab; link menus', opened.startsWith('other.md') && after.length === before.length + 1 && after.some(t => t.startsWith('long.md'))
    && linkMenu.join() === 'Copy Link Address,Copy Link Text' && copied === want4
    && entryMenu.join() === 'Copy Link Address,Copy Link Text' && entryCopied === wantEntry && textMenu.includes('Copy'),
    `active "${opened}", tabs ${before.length} → ${after.length}; menu on the link [${linkMenu}], copied "${copied}"; `
    + `menu on a sidebar entry [${entryMenu}], copied "${entryCopied}"; menu on text [${textMenu}]`);

// 5 the extension's Markdown button on the preview; Ctrl+Shift+V from the source back to the preview
const buttons = await titleActions();
const markdownButton = buttons.includes('Markdown');
await ev(c, s, `[...${group}.querySelectorAll('.editor-actions .action-label')].find(e => /^Show Source/.test(e.getAttribute('aria-label') || '')).click(), 1`);
await sleep(2000);
const sourceIndex = await activeIndex();
// Cursor shows its own Preview / Markdown switch (.markdown-mode-tab) over any .md editor, the preview too
const sourceKind = await textShown() ? 'the source' : 'no source editor';
const previewButton = (await titleActions()).includes('Preview');
const r5 = await ev(c, s, `(() => { const e = [...${group}.querySelectorAll('.monaco-editor .view-lines')].find(e => e.getBoundingClientRect().width > 0); if (!e) return null; const r = e.getBoundingClientRect(); return [r.x + 100, r.y + 50]; })()`);
if (r5) {
    await click(c, s, ...r5);
}
await key('V', 'KeyV', 86, 2 | 8);
await sleep(2500);
const switched = await previewShown() && !await textShown();
check(5, 'Preview / Markdown buttons and Ctrl+Shift+V', markdownButton && previewButton && switched,
    `Markdown button on the preview ${markdownButton ? 'present' : 'missing'}; Show Source opened ${sourceKind}, Preview button ${previewButton ? 'present' : 'missing'}; Ctrl+Shift+V ${switched ? 'switched back to the preview' : 'did nothing'}`);
if (!switched) {
    await closeTab(sourceIndex);
}
await clickTab(home);

// 6 a double click stays in the preview; Meta+double-click opens the source
w = await preview(c, LINK);
await click(c, s, ...await at(w, `${page}.document.querySelectorAll('.markdown-body p')[8]`), { count: 2 });
await sleep(1500);
const stays = await previewShown() && !await textShown();
await click(c, s, ...await at(w, `${page}.document.querySelectorAll('.markdown-body p')[8]`), { count: 2, modifiers: 4 });
await sleep(2000);
const opens = await textShown();
check(6, 'only Cmd (Meta) + double-click opens the source', stays && opens, `double click ${stays ? 'stays' : 'left the preview'}; Meta+double-click ${opens ? 'opens the source' : 'does not'}`);
if (opens) {
    await closeTab(await activeIndex());
}
await clickTab(home);

// 7 diff colours as in the editor, no row background; first table column on one line
w = await preview(c, LINK);
const style = await ev(c, w.sessionId, `(() => {
    const d = ${page}.document;
    const cs = e => ${page}.getComputedStyle(e);
    const add = d.querySelector('.hljs-addition'), del = d.querySelector('.hljs-deletion');
    const td = d.querySelector('.markdown-body table tbody td');
    const range = d.createRange(); range.selectNodeContents(td);
    return { light: d.body.classList.contains('vscode-light'), add: cs(add).color, del: cs(del).color, bg: cs(add).backgroundColor,
             lines: new Set([...range.getClientRects()].map(r => Math.round(r.top))).size };
})()`);
const want = style.light ? ['rgb(9, 134, 88)', 'rgb(163, 21, 21)'] : ['rgb(181, 206, 168)', 'rgb(206, 145, 120)'];
check(7, 'diff colours and table', style.add === want[0] && style.del === want[1] && style.bg === 'rgba(0, 0, 0, 0)' && style.lines === 1,
    `${style.light ? 'light' : 'dark'} theme: added ${style.add}, removed ${style.del}, background ${style.bg}; first column ${style.lines} line(s)`);

// 13 the Copy button of a diff block, clicked with the mouse: the clipboard gets the block's lines as the file has
// them (with the +/-, without the line break after the last line), the button says Copied, then Copy again
w = await preview(c, LINK);
const DIFF = `${page}.document.querySelectorAll('.markdown-body pre > code.language-diff')[69]`;
const BUTTON = `${DIFF}.parentElement.previousElementSibling.querySelector('mpp-copy > button')`;
// the lines between the block's fences in the file; data-line is the opening fence's line, counted from 0
const fence = await ev(c, w.sessionId, `Number(${DIFF}.dataset.line)`);
const fileLines = fs.readFileSync(new URL(source), 'utf8').split('\n').slice(fence + 1);
const want8 = fileLines.slice(0, fileLines.indexOf('```')).join('\n');
const copyLabel = () => ev(c, w.sessionId, `${page}.getComputedStyle(${BUTTON}, '::before').content.replace(/"/g, '')`);
if (await ev(c, w.sessionId, `!${BUTTON}`)) {
    check(13, 'Copy button on a diff block', false, 'the block has no Copy button');
} else {
    await ev(c, s, `navigator.clipboard.writeText('before check 8')`);
    await click(c, s, ...await at(w, BUTTON));
    await sleep(500);
    const label = await copyLabel();
    const copied = await ev(c, s, `navigator.clipboard.readText()`);
    await sleep(1500);
    const later = await copyLabel();
    check(13, 'Copy button on a diff block', copied === want8 && label === 'Copied' && later === 'Copy',
        `clipboard ${copied === want8 ? `= the block's ${want8.split('\n').length} lines in the file` : JSON.stringify(copied)}; button "${label}", 2 s later "${later}"`);
}

// 14 links to source lines as of a commit (?v=) in other.md: line 20, moved to 23 since by lines added at the top,
// opens the file in the worktree at 23 and the status bar says so; line 40, changed since, opens the file in the worktree
// with the line in its place (43) selected, and a notification whose Show as of button opens the file as of the commit
// at 40
await click(c, s, ...await at(w, `${page}.document.querySelector('a[href$="other.md"]')`));
await sleep(2000);
const otherIndex = await activeIndex();
const selection = () => ev(c, s, `document.querySelector('[id="status.editor.selection"]')?.innerText`);
// the text of the line the cursor is on in the editor shown
const cursorLine = () => ev(c, s, `(() => { const ed = [...${group}.querySelectorAll('.monaco-editor')].find(e => e.getBoundingClientRect().width > 0); const cur = ed?.querySelector('.cursors-layer .cursor');
    return cur ? [...ed.querySelectorAll('.view-lines .view-line')].find(l => l.style.top === cur.style.top)?.innerText.replace(/\\u00a0/g, ' ') : null; })()`);
// In the notification center (the bell at the right of the status bar opens and closes it), the notification whose text
// starts with <prefix>: click its button <label>; returns the notification's text, or null when there is none
async function pressButton(prefix, label) {
    const bell = async () => {
        await click(c, s, ...await ev(c, s, `(() => { const r = document.getElementById('status.notifications').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`));
        await sleep(700);
    };
    await bell();
    const found = await ev(c, s, `(() => {
        const e = [...document.querySelectorAll('.notification-list-item')].find(e => e.querySelector('.notification-list-item-message')?.innerText.startsWith(${JSON.stringify(prefix)}));
        const b = e && [...e.querySelectorAll('.monaco-button')].find(b => b.innerText === ${JSON.stringify(label)});
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return { text: e.querySelector('.notification-list-item-message').innerText, at: [r.x + r.width / 2, r.y + r.height / 2] };
    })()`);
    if (found) {
        await click(c, s, ...found.at);
        await sleep(2000);
    }
    if (await ev(c, s, `[...document.querySelectorAll('.notifications-center')].some(e => e.getBoundingClientRect().height > 0)`)) {
        await bell();
    }
    return found && found.text;
}
async function openPinned(line) {
    await clickTab(otherIndex);
    const o = await preview(c, 'a[href*="pinned.cpp?v="]');
    await click(c, s, ...await at(o, `${page}.document.querySelector('a[href*="pinned.cpp?v="][href$="#L${line}"]')`));
    await sleep(2000);
    return { tab: (await tabs())[await activeIndex()], selection: await selection(), text: await cursorLine(),
             message: await ev(c, s, `[...document.querySelectorAll('.statusbar-item')].map(e => e.innerText).find(t => / now$/.test(t)) || ''`) };
}
const pinnedCommit = (await ev(c, (await preview(c, 'a[href*="pinned.cpp?v="]')).sessionId,
    `${page}.document.querySelector('a[href*="pinned.cpp?v="]').getAttribute('href')`)).match(/\?v=(\w+)/)[1];
const moved = await openPinned(20);
await closeTab(await activeIndex());
const changed = await openPinned(40);
changed.note = await pressButton('pinned.cpp:40 ', 'Show as of ' + pinnedCommit);
const asOf = { tab: (await tabs())[await activeIndex()], selection: await selection(), text: await cursorLine() };
// the file as of the commit, then the file in the worktree
for (let i = 0; i < 2 && (await tabs())[await activeIndex()].startsWith('pinned.cpp'); i++) {
    await closeTab(await activeIndex());
}
check(14, 'links to source lines as of a commit', moved.tab.startsWith('pinned.cpp') && moved.selection === 'Ln 23, Col 1'
    && moved.text.startsWith('int cited_20 = 20;') && moved.message.endsWith(' is line 23 now')
    && changed.tab.startsWith('pinned.cpp') && /^Ln 43, Col \d+ \(\d+ selected\)$/.test(changed.selection) && changed.text.startsWith('int cited_40 = 41;')
    && changed.note === `pinned.cpp:40 changed after ${pinnedCommit}; these are the lines that replaced it in the worktree.`
    && asOf.tab.startsWith('pinned.cpp') && asOf.selection === 'Ln 40, Col 1' && asOf.text.startsWith('int cited_40 = 40;'),
    `line 20: "${moved.tab}" ${moved.selection} "${moved.text}", status bar "${moved.message}"; `
    + `line 40: "${changed.tab}" ${changed.selection} "${changed.text}", notification ${JSON.stringify(changed.note)}; `
    + `its Show as of button: "${asOf.tab}" ${asOf.selection} "${asOf.text}"`);

// 15 links to file.md#anchor in other.md, to anchors.md#run-25 (an <a id> in a table row) and anchors.md#run-log (a
// heading), each once with anchors.md closed (a new tab opens at the anchor) and once with it open but covered (it
// scrolls there in place, the page not rebuilt)
async function follow(id) {
    await clickTab(otherIndex);
    const o = await preview(c, 'a[href*="pinned.cpp?v="]');
    await click(c, s, ...await at(o, `${page}.document.querySelector('a[href="anchors.md#${id}"]')`));
    await sleep(3000);
    const t = await preview(c, '#run-25');
    const r = await ev(c, t.sessionId, `({ top: Math.round(${page}.document.getElementById('${id}').getBoundingClientRect().top) + 0, kept: ${page}.__mppMark === 'kept' })`);
    await ev(c, t.sessionId, `${page}.__mppMark = 'kept', 1`);
    return { tab: (await tabs())[await activeIndex()], ...r };
}
const followed = [['run-25', 'closed', await follow('run-25')], ['run-log', 'covered', await follow('run-log')]];
await closeTab(await activeIndex());
followed.push(['run-log', 'closed', await follow('run-log')], ['run-25', 'covered', await follow('run-25')]);
await closeTab(await activeIndex());
await closeTab(otherIndex);
await clickTab(home);
check(15, 'links to file.md#anchor', followed.every(([, state, r]) => r.tab.startsWith('anchors.md') && r.top >= 0 && r.top < 150 && (state === 'closed' || r.kept)),
    followed.map(([id, state, r]) => `#${id} with anchors.md ${state}: "${r.tab}", the anchor at ${r.top}px${state === 'covered' ? (r.kept ? ', page kept' : ', page rebuilt') : ''}`).join('; '));

// 16 Back to another file: in other.md click the link to anchors.md#run-log, with anchors.md closed; anchors.md shows
// ↩ Back, and the Go Back key (Ctrl+Alt+←) there returns to other.md; again with anchors.md open but covered, back
// with the ↩ Back button. The jumps the earlier checks made are forgotten first.
await ev(c, w.sessionId, `${page}.localStorage.removeItem('md-preview-plus-file-jumps'), 1`);
await click(c, s, ...await at(w, `${page}.document.querySelector('a[href$="other.md"]')`));
await sleep(2000);
const from16 = await activeIndex();
async function toAnchors() {
    await clickTab(from16);
    const o = await preview(c, 'a[href*="pinned.cpp?v="]');
    await click(c, s, ...await at(o, `${page}.document.querySelector('a[href="anchors.md#run-log"]')`));
    await sleep(3000);
    const t = await preview(c, '#run-25');
    return { t, back: await ev(c, t.sessionId, `!${page}.document.getElementById('mpp-back').hidden`) };
}
const closed16 = await toAnchors();
// a click on plain text in view puts the keyboard in anchors.md's page
await click(c, s, ...await at(closed16.t, `[...${page}.document.querySelectorAll('.markdown-body :is(h2, p, td)')].find(e => { const r = e.getBoundingClientRect(); return r.top > 80 && r.bottom < ${page}.innerHeight - 50; })`, false));
await sleep(300);
await key('ArrowLeft', 'ArrowLeft', 37, 1 | 2);
await sleep(2000);
const byKey = (await tabs())[await activeIndex()];
const covered16 = await toAnchors();
if (covered16.back) {
    await click(c, s, ...await at(covered16.t, `${page}.document.getElementById('mpp-back')`, false));
    await sleep(2000);
}
const byButton = (await tabs())[await activeIndex()];
await closeTab((await tabs()).findIndex(t => t.startsWith('anchors.md')));
await closeTab((await tabs()).findIndex(t => t.startsWith('other.md')));
await clickTab(home);
check(16, 'Back to another file', closed16.back && byKey.startsWith('other.md') && covered16.back && byButton.startsWith('other.md'),
    `anchors.md closed: its ↩ Back ${closed16.back ? 'shown' : 'missing'}, Ctrl+Alt+← went to "${byKey}"; `
    + `anchors.md covered: its ↩ Back ${covered16.back ? 'shown' : 'missing'}, the button went to "${byButton}"`);

c.close();
process.exit(results.every(Boolean) ? 0 : 1);
