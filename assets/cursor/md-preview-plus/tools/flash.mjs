// Measure what the screen shows when a covered Markdown preview tab is shown again: click a link in the
// preview that opens a code file in the same group (covering the preview), click the preview's tab to go
// back, and record every frame the window paints from then on, plus what the preview page itself saw
// (resizes, long frames). The preview must be the active tab, with the link somewhere in the document.
//   node flash.mjs <out dir> <link target, e.g. CmdTeardownHca.cpp#L79>
// Writes <out dir>/fNNN_<ms after the click on the tab>.png and summary.json; read them with analyze.py.
import { connect, workbench, sleep, prepare } from './cdp.mjs';
import fs from 'fs';

const [OUT, TARGET] = process.argv.slice(2);
fs.mkdirSync(OUT, { recursive: true });
const c = await connect();
const s = await workbench(c);

async function ev(session, expression) {
    const r = await c.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, session);
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 1500));
    return r.result.value;
}
async function click(x, y) {
    for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
        await c.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: type === 'mouseMoved' ? 0 : 1 }, s);
    }
}
const LINK = `a[href*="${TARGET}"], a[data-href*="${TARGET}"]`;

await prepare(c, s);

// the webview (an iframe target) that holds the preview with the link
const { targetInfos } = await c.send('Target.getTargets');
let w;
for (const t of targetInfos.filter(t => t.type === 'iframe' && t.url.startsWith('vscode-webview://'))) {
    const { sessionId } = await c.send('Target.attachToTarget', { targetId: t.targetId, flatten: true });
    if (await ev(sessionId, `!!document.getElementById('active-frame')?.contentDocument?.querySelector('${LINK}')`)) {
        w = { sessionId, id: new URL(t.url).searchParams.get('id') };
        break;
    }
}
if (!w) throw new Error('no preview webview with the link');

// instrument the page: resize / visibility / scroll / gaps between animation frames, in wall-clock time
await ev(w.sessionId, `(() => {
    const win = document.getElementById('active-frame').contentWindow;
    const log = win.__mppLog = [];
    const now = () => Date.now();
    win.addEventListener('resize', () => log.push(['resize', now(), win.innerWidth, win.innerHeight, Math.round(win.scrollY)]));
    win.document.addEventListener('visibilitychange', () => log.push(['visibility', now(), win.document.visibilityState]));
    win.addEventListener('scroll', () => log.push(['scroll', now(), Math.round(win.scrollY)]));
    let last = 0;
    const loop = ts => { const t = now(); if (last && t - last > 40) log.push(['raf-gap', last, t, t - last]); last = t; win.requestAnimationFrame(loop); };
    win.requestAnimationFrame(loop);
    win.document.querySelector('${LINK}').scrollIntoView({ block: 'center' });
    return true;
})()`);
await sleep(600);

// the link's position in the window: the webview iframe in the workbench + the link in its content frame
const iframe = `[...document.querySelectorAll('iframe')].find(f => f.src.includes('${w.id}'))`;
const frameRect = await ev(s, `(() => { const r = ${iframe}.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })()`);
const linkRect = await ev(w.sessionId, `(() => { const af = document.getElementById('active-frame'); const o = af.getBoundingClientRect(); const r = af.contentDocument.querySelector('${LINK}').getBoundingClientRect(); return [o.x + r.x, o.y + r.y, r.width, r.height]; })()`);
const before = await ev(w.sessionId, `document.getElementById('active-frame').contentWindow.scrollY`);
// the preview's tab, found again later by its place among the tabs
const tabIndex = await ev(s, `[...document.querySelectorAll('.tab')].indexOf(document.querySelector('.editor-group-container.active .tab.active'))`);
await click(frameRect[0] + linkRect[0] + Math.min(linkRect[2] / 2, 40), frameRect[1] + linkRect[1] + linkRect[3] / 2);
const file = TARGET.split('#')[0].split('/').pop();
for (let i = 0; i < 40 && !(await ev(s, 'document.title')).includes(file); i++) await sleep(100);
await sleep(1500);
// where the link put the cursor in the code file, as the status bar shows it ("Ln 79, Col 1")
const cursor = await ev(s, `document.querySelector('[id="status.editor.selection"]')?.innerText`);
// the covered preview: its iframe size (300x150 means the anchor was lost) and its container's styles
const covered = await ev(s, `(() => { const f = ${iframe}; const r = f.getBoundingClientRect(); const cont = f.parentElement; const cs = getComputedStyle(cont); return { iframe: [r.x, r.y, r.width, r.height], container: [cont.style.visibility, cs.width, cs.height, cs.top, cs.left] }; })()`);

// record frames while going back
const frames = [];
c.on(msg => {
    if (msg.method === 'Page.screencastFrame' && msg.sessionId === s) {
        const { data, metadata, sessionId } = msg.params;
        frames.push({ t: Math.round(metadata.timestamp * 1000), data });
        c.send('Page.screencastFrameAck', { sessionId }, s);
    }
});
await c.send('Page.startScreencast', { format: 'png', everyNthFrame: 1 }, s);
await sleep(700);
const tBack = Date.now();
const tab = await ev(s, `(() => { const r = document.querySelectorAll('.tab')[${tabIndex}].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
await click(tab[0], tab[1]);
await sleep(2500);
await c.send('Page.stopScreencast', {}, s);
const after = await ev(w.sessionId, `document.getElementById('active-frame').contentWindow.scrollY`);
const shown = await ev(s, `(() => { const r = ${iframe}.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })()`);
const log = await ev(w.sessionId, `document.getElementById('active-frame').contentWindow.__mppLog`);

// times relative to the click on the tab: frames, resize events, raf gaps (start and end)
frames.forEach((f, i) => fs.writeFileSync(`${OUT}/f${String(i).padStart(3, '0')}_${f.t - tBack}.png`, Buffer.from(f.data, 'base64')));
const rel = e => [e[0], ...e.slice(1).map((v, i) => (i === 0 || (e[0] === 'raf-gap' && i === 1)) && typeof v === 'number' ? v - tBack : v)];
const summary = { cursor, scroll: { before, after }, covered, shown, frames: frames.map(f => f.t - tBack), log: log.map(rel) };
fs.writeFileSync(`${OUT}/summary.json`, JSON.stringify(summary, null, 1));
console.log(JSON.stringify(summary));
c.close();
