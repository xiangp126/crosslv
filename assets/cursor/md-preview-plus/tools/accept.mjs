// Acceptance checks 1-7 of plans/md-preview-plus.md §7.3, in the Cursor that start.sh started, with the preview of
// long.md from make_sample.py as the active tab. Prints PASS or FAIL per check; exits 1 if any failed.
// On Linux the keys are Ctrl+F and Ctrl+Shift+V; the Cmd of Cmd+double-click is Meta.
//   node accept.mjs
import { connect, workbench, sleep, ev, click, prepare, preview } from './cdp.mjs';

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
// window coordinates of the middle of the element <expr> evaluates to in the preview page
async function at(w, expr) {
    const f = await ev(c, s, `(() => { const r = [...document.querySelectorAll('iframe')].find(f => f.src.includes('${w.id}')).getBoundingClientRect(); return [r.x, r.y]; })()`);
    const e = await ev(c, w.sessionId, `(() => { const af = document.getElementById('active-frame'); const o = af.getBoundingClientRect(); const el = (${expr}); el.scrollIntoView({ block: 'center' }); const r = el.getBoundingClientRect(); return [o.x + r.x + Math.min(r.width / 2, 40), o.y + r.y + r.height / 2]; })()`);
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

// 2 sidebar: click the entry of section 70, the heading comes to the top
const entries = await ev(c, w.sessionId, `${page}.document.querySelectorAll('#mpp-sidebar a').length`);
await click(c, s, ...await at(w, `[...${page}.document.querySelectorAll('#mpp-sidebar a')].find(a => a.textContent.includes('70. 第 70 节'))`));
await sleep(1000);
const top = await ev(c, w.sessionId, `Math.round([...${page}.document.querySelectorAll('h2')].find(h => h.textContent.includes('70. 第 70 节')).getBoundingClientRect().top)`);
const resize = await ev(c, w.sessionId, `!!${page}.document.getElementById('mpp-resize')`);
check(2, 'sidebar', entries > 80 && top >= 0 && top < 150 && resize, `${entries} entries; section 70 at ${top}px after the click; drag bar ${resize ? 'present' : 'missing'}`);

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

// 4 a link to another .md opens a new tab and leaves this one
const before = await tabs();
await click(c, s, ...await at(w, `${page}.document.querySelector('a[href$="other.md"]')`));
await sleep(2000);
const after = await tabs();
const opened = after[await activeIndex()];
check(4, 'md link opens a new tab', opened.startsWith('other.md') && after.length === before.length + 1 && after.some(t => t.startsWith('long.md')), `active "${opened}", tabs ${before.length} → ${after.length}`);
await closeTab(await activeIndex());
await clickTab(home);

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

c.close();
process.exit(results.every(Boolean) ? 0 : 1);
