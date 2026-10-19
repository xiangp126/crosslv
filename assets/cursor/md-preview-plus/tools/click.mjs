// Click at window coordinates <x> <y> in the Cursor window, as a real mouse would.
//   node click.mjs <x> <y>
import { connect, workbench, sleep } from './cdp.mjs';
const c = await connect();
const s = await workbench(c);
const [x, y] = process.argv.slice(2).map(Number);
for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
    await c.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: type === 'mouseMoved' ? 0 : 1 }, s);
}
await sleep(500);
c.close();
