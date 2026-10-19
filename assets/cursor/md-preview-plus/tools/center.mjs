// Wait for the workbench, then <seconds> more (default 40), and print what the notification center holds.
import { connect, workbench, sleep } from './cdp.mjs';

const seconds = Number(process.argv[2] || 40);
let c, s;
for (let i = 0; i < 90 && !s; i++) {
    try {
        c = c || await connect();
        s = await workbench(c);
    } catch {
        await sleep(1000);
    }
}
await sleep(seconds * 1000);
const evaluate = async expr => (await c.send('Runtime.evaluate', { expression: expr, returnByValue: true }, s)).result.value;
const items = () => evaluate(`[...document.querySelectorAll('.notification-list-item')].map(e => e.innerText.replace(/\\s+/g, ' '))`);
await evaluate(`document.querySelectorAll('.onboarding-v2-overlay').forEach(e => e.style.display = 'none'), 1`);
let list = await items();
if (list.length === 0) {
    const bell = await evaluate(`(() => { const r = document.querySelector('[class*=codicon-bell]').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
    for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
        await c.send('Input.dispatchMouseEvent', { type, x: bell[0], y: bell[1], button: 'left', clickCount: type === 'mouseMoved' ? 0 : 1 }, s);
    }
    await sleep(500);
    list = await items();
}
console.log(JSON.stringify(list, null, 1));
c.close();
