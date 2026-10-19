// Minimal CDP client over the browser websocket, flat sessions, and the steps the test scripts share.
export async function connect(port = 9339) {
    const ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    const ws = new WebSocket(ver.webSocketDebuggerUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    let id = 0;
    const pending = new Map();
    const listeners = [];
    ws.onmessage = ev => {
        const msg = JSON.parse(ev.data);
        if (msg.id && pending.has(msg.id)) {
            const { res, rej } = pending.get(msg.id);
            pending.delete(msg.id);
            msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
        } else if (msg.method) {
            for (const l of listeners) l(msg);
        }
    };
    const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
        const m = { id: ++id, method, params };
        if (sessionId) m.sessionId = sessionId;
        pending.set(m.id, { res, rej });
        ws.send(JSON.stringify(m));
    });
    const on = fn => listeners.push(fn);
    const close = () => ws.close();
    return { send, on, close };
}

export async function workbench(c) {
    const { targetInfos } = await c.send('Target.getTargets');
    const page = targetInfos.find(t => t.type === 'page' && t.url.includes('workbench'));
    const { sessionId } = await c.send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
    return sessionId;
}

export const sleep = ms => new Promise(r => setTimeout(r, ms));

// Evaluate an expression in a session (the workbench, or a webview) and return its value.
export async function ev(c, session, expression) {
    const r = await c.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, session);
    if (r.exceptionDetails) {
        throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 1500));
    }
    return r.result.value;
}

// A real mouse click at window coordinates; modifiers: 1 Alt, 2 Ctrl, 4 Meta, 8 Shift.
export async function click(c, s, x, y, { count = 1, modifiers = 0 } = {}) {
    await c.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, modifiers }, s);
    for (let n = 1; n <= count; n++) {
        for (const type of ['mousePressed', 'mouseReleased']) {
            await c.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: n, modifiers }, s);
        }
    }
}

// Get the window ready for a test: hide Cursor's log-in screen (shown when no account is logged in) and
// close the Agents panel, which squeezes the editor to under 500 px. Returns the widest webview's width.
export async function prepare(c, s) {
    await ev(c, s, `document.querySelectorAll('.onboarding-v2-overlay').forEach(e => e.style.display = 'none'), 1`);
    const agentsOpen = `(document.querySelector('.part.auxiliarybar')?.getBoundingClientRect().width || 0) > 0`;
    if (await ev(c, s, agentsOpen)) {
        await ev(c, s, `[...document.querySelectorAll('.titlebar-container .action-label')].find(e => /^Toggle Agents/.test(e.getAttribute('aria-label') || '')).click(), 1`);
        await sleep(1500);
        if (await ev(c, s, agentsOpen)) {
            throw new Error('the Agents panel is still open');
        }
    }
    return ev(c, s, `Math.round(Math.max(0, ...[...document.querySelectorAll('iframe.webview')].map(f => f.getBoundingClientRect().width)))`);
}

// The webview of the Markdown preview whose page has <selector> in it: { sessionId, id }, or null.
export async function preview(c, selector = '.markdown-body') {
    const { targetInfos } = await c.send('Target.getTargets');
    for (const t of targetInfos.filter(t => t.type === 'iframe' && t.url.startsWith('vscode-webview://'))) {
        const { sessionId } = await c.send('Target.attachToTarget', { targetId: t.targetId, flatten: true });
        if (await ev(c, sessionId, `!!document.getElementById('active-frame')?.contentDocument?.querySelector(${JSON.stringify(selector)})`)) {
            return { sessionId, id: new URL(t.url).searchParams.get('id') };
        }
    }
    return null;
}
