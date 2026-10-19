// Save a screenshot of the Cursor window (look at it with an image viewer, or the Read tool).
//   node shot.mjs <file.png>
import { connect, workbench } from './cdp.mjs';
import fs from 'fs';
const c = await connect();
const s = await workbench(c);
const out = process.argv[2] || 'shot.png';
const { data } = await c.send('Page.captureScreenshot', { format: 'png' }, s);
fs.writeFileSync(out, Buffer.from(data, 'base64'));
const r = await c.send('Runtime.evaluate', { expression: 'JSON.stringify({w: innerWidth, h: innerHeight, title: document.title})', returnByValue: true }, s);
console.log(r.result.value);
c.close();
