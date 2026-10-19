// Test the third preview patch (update covered tabs in place): with the preview of <md file> active,
// click a link in it that opens a code file in the same group (covering the preview), append a line to
// the md file on disk, go back to the preview, and report whether the page took the change in place:
// the same page (not rebuilt), the new line shown, the scroll position kept. The md file is restored.
//   node covered_update.mjs <md file> <link target in it, e.g. sample.cpp#L79>
// Passes when: rebuilt false, updated true, scroll before == after.
import { connect, workbench, sleep, prepare } from './cdp.mjs';
import fs from 'fs';

const [MD, TARGET] = process.argv.slice(2);
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
const page = `document.getElementById('active-frame').contentWindow`;

// mark the page: a rebuilt page loses the mark
await ev(w.sessionId, `(${page}.__mppMark = 'kept', ${page}.document.querySelector('${LINK}').scrollIntoView({ block: 'center' }), 1)`);
await sleep(600);
const before = await ev(w.sessionId, `${page}.scrollY`);
const tabIndex = await ev(s, `[...document.querySelectorAll('.tab')].indexOf(document.querySelector('.editor-group-container.active .tab.active'))`);
const iframe = `[...document.querySelectorAll('iframe')].find(f => f.src.includes('${w.id}'))`;
const frameRect = await ev(s, `(() => { const r = ${iframe}.getBoundingClientRect(); return [r.x, r.y]; })()`);
const linkRect = await ev(w.sessionId, `(() => { const af = document.getElementById('active-frame'); const o = af.getBoundingClientRect(); const r = af.contentDocument.querySelector('${LINK}').getBoundingClientRect(); return [o.x + r.x, o.y + r.y, r.width, r.height]; })()`);
await click(frameRect[0] + linkRect[0] + Math.min(linkRect[2] / 2, 40), frameRect[1] + linkRect[1] + linkRect[3] / 2);
await sleep(2000);

// change the file while the preview is covered
const original = fs.readFileSync(MD, 'utf8');
const marker = 'covered-update-' + Date.now();
fs.writeFileSync(MD, original + '\n' + marker + '\n');
await sleep(2000);

const tab = await ev(s, `(() => { const r = document.querySelectorAll('.tab')[${tabIndex}].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
await click(tab[0], tab[1]);
await sleep(2500);
const result = await ev(w.sessionId, `({ rebuilt: ${page}.__mppMark !== 'kept', updated: ${page}.document.body.innerText.includes('${marker}'), scroll: { before: ${before}, after: ${page}.scrollY } })`);
fs.writeFileSync(MD, original);
console.log(JSON.stringify(result));
c.close();
