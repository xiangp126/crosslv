// Evaluate a JavaScript expression in the Cursor window (the workbench page) and print the result.
//   node eval.mjs '<expression>'
import { connect, workbench } from './cdp.mjs';
const c = await connect();
const s = await workbench(c);
const expr = process.argv[2];
const r = await c.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }, s);
console.log(r.exceptionDetails ? JSON.stringify(r.exceptionDetails).slice(0, 2000) : (typeof r.result.value === 'string' ? r.result.value : JSON.stringify(r.result.value, null, 1)));
c.close();
