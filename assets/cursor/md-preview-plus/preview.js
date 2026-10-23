// Built-in Markdown preview: a heading sidebar on the left, rebuilt whenever the text changes, a
// find box, since Cursor's own find does not work in the preview, a Back for jumps inside the
// page and from other files' pages, and a Copy button on every code block. The preview keeps the
// rendered text in .markdown-body; the sidebar, the find box and the Back button live outside it, so the
// preview's updates leave them in place. The Copy buttons sit next to the code blocks, so each update
// drops them: they are added again.
(function () {
    'use strict';
    const HIDDEN_KEY = 'md-preview-plus-sidebar-hidden';
    const WIDTH_KEY = 'md-preview-plus-sidebar-width';
    const HISTORY_KEY = 'md-preview-plus-find-history';
    const OPTIONS_KEY = 'md-preview-plus-find-options';
    const JUMPS_KEY = 'md-preview-plus-file-jumps';
    // a jump from another file counts for an hour after the click
    const JUMP_LIFETIME = 60 * 60 * 1000;
    const LEVELS = 'h1, h2, h3, h4';
    // our own nodes; changes inside them are not changes of the page
    const OWN = '#mpp-sidebar, #mpp-toggle, #mpp-resize, #mpp-find, #mpp-back, #mpp-back-link, mpp-copy, #mpp-copy-text';
    const IS_MAC = /Mac/.test(navigator.platform);
    const IS_LINUX = /Linux/.test(navigator.platform);
    const FIND_MOD = IS_MAC ? 'metaKey' : 'ctrlKey';
    const BACK_KEY_NAME = IS_MAC ? '⌃⌥← or ⌃-' : IS_LINUX ? 'Ctrl+Alt+← or Ctrl+Alt+-' : 'Alt+← or Ctrl+Alt+←';
    const CAN_HIGHLIGHT = Boolean(window.Highlight && window.CSS && CSS.highlights);
    // the editor's default word separators, for "match whole word"
    const SEPARATORS = '`~!@#$%^&*()-=+[{]}\\|;:\'",.<>/?';
    let nav, list, headings = [], links = [], pending = false;
    let findBox, findInput, findCount, matches = [], matchIndex = 0, findHistory = [], rememberTimer;
    let findOptions = { matchCase: false, wholeWord: false }, optionButtons = {};
    let backButton, backStack = [], backTimer;

    function storedHidden() {
        try { return localStorage.getItem(HIDDEN_KEY) === '1'; } catch (e) { return false; }
    }

    function setHidden(hidden) {
        try { localStorage.setItem(HIDDEN_KEY, hidden ? '1' : '0'); } catch (e) { /* no storage: per-load only */ }
        document.body.classList.toggle('mpp-on', !hidden);
    }

    // Sidebar width in px, kept between 140 px and 60% of the window; remembered across previews.
    function setWidth(px) {
        const width = Math.max(140, Math.min(Math.round(px), Math.floor(window.innerWidth * 0.6)));
        document.documentElement.style.setProperty('--mpp-width', width + 'px');
        return width;
    }

    // The bar between the sidebar and the text: drag it to resize the sidebar.
    function makeResizer() {
        const bar = document.createElement('div');
        bar.id = 'mpp-resize';
        bar.title = 'Drag to resize the table of contents';
        bar.addEventListener('mousedown', down => {
            down.preventDefault();
            document.body.classList.add('mpp-resizing');
            let width = 0;
            const move = e => {
                width = setWidth(e.clientX);
            };
            const up = () => {
                document.removeEventListener('mousemove', move);
                document.removeEventListener('mouseup', up);
                document.body.classList.remove('mpp-resizing');
                if (width) {
                    try { localStorage.setItem(WIDTH_KEY, String(width)); } catch (e) { /* no storage */ }
                }
            };
            document.addEventListener('mousemove', move);
            document.addEventListener('mouseup', up);
        });
        return bar;
    }

    function ensureSidebar() {
        if (nav && document.body.contains(nav)) {
            return;
        }
        nav = document.createElement('nav');
        nav.id = 'mpp-sidebar';
        // a double click in the preview opens the source at that line; not from the sidebar
        nav.addEventListener('dblclick', e => e.stopPropagation());
        list = document.createElement('div');
        nav.appendChild(list);
        const toggle = document.createElement('button');
        toggle.id = 'mpp-toggle';
        toggle.type = 'button';
        toggle.title = 'Show / hide the table of contents';
        toggle.textContent = '☰';
        toggle.addEventListener('click', () => setHidden(document.body.classList.contains('mpp-on')));
        // clicking it twice quickly is a double click, which the preview turns into "open the source"
        toggle.addEventListener('dblclick', e => e.stopPropagation());
        document.body.appendChild(nav);
        document.body.appendChild(makeResizer());
        document.body.appendChild(toggle);
        try {
            const stored = Number(localStorage.getItem(WIDTH_KEY));
            if (stored > 0) {
                setWidth(stored);
            }
        } catch (e) { /* no storage: default width */ }
        setHidden(storedHidden());
    }

    // Back: a click on a link to a place in this page, or on a sidebar entry, first remembers where the
    // page was; the editor's Go Back key or the Back button at the bottom right returns there, one jump
    // at a time. A click on a link to another .md file is remembered as well, in localStorage, which all the
    // previews share: for an hour, the Back of that file's page returns to this file, when that jump is newer than
    // the newest jump inside its own page.
    function ensureBack() {
        if (backButton && document.body.contains(backButton)) {
            return;
        }
        backButton = document.createElement('button');
        backButton.id = 'mpp-back';
        backButton.type = 'button';
        backButton.textContent = '↩ Back';
        backButton.title = 'Back to where the link was clicked (' + BACK_KEY_NAME + ')';
        backButton.addEventListener('click', goBack);
        backButton.addEventListener('dblclick', e => e.stopPropagation());
        document.body.appendChild(backButton);
        updateBack();
    }

    function rememberPosition() {
        backStack = backStack.concat({ y: window.scrollY, time: Date.now() }).slice(-50);
        backButton.hidden = false;
    }

    function goBack() {
        const jumps = fileJumps(), i = fileJumpBack(jumps);
        if (i >= 0) {
            const from = jumps[i].from;
            jumps.splice(i, 1);
            saveFileJumps(jumps);
            openFile(from);
        } else if (backStack.length > 0) {
            window.scrollTo(0, backStack.pop().y);
        }
        updateBack();
    }

    function canGoBack() {
        return backStack.length > 0 || fileJumpBack(fileJumps()) >= 0;
    }

    // The button shows while there is something to go back to; a jump from another file stops counting when it
    // expires, so look again then.
    function updateBack() {
        const jumps = fileJumps(), i = fileJumpBack(jumps);
        backButton.hidden = backStack.length === 0 && i < 0;
        clearTimeout(backTimer);
        if (i >= 0) {
            backTimer = setTimeout(updateBack, jumps[i].time + JUMP_LIFETIME - Date.now());
        }
    }

    // This page's file: the URL the preview renders it from (file:, vscode-remote: and the like)
    function pageUrl() {
        const settings = document.getElementById('vscode-markdown-preview-data').getAttribute('data-settings');
        return new URL(JSON.parse(settings).source);
    }

    // The jumps from one file's page to another's in the last hour, { from, to, time } with the files' absolute paths,
    // oldest first. Older ones are left out, so the next save drops them.
    function fileJumps() {
        try {
            const now = Date.now();
            return (JSON.parse(localStorage.getItem(JUMPS_KEY)) || []).filter(jump => now - jump.time < JUMP_LIFETIME);
        } catch (e) {
            return [];
        }
    }

    function saveFileJumps(jumps) {
        try {
            localStorage.setItem(JUMPS_KEY, JSON.stringify(jumps.slice(-50)));
        } catch (e) { /* no storage: no Back to the other file */ }
    }

    // A click on a link to another .md file, which the preview opens in that file's own tab: remember the jump
    function rememberFileJump(a) {
        const raw = a.getAttribute('data-href') || a.getAttribute('href');
        if (!raw || raw.startsWith('#') || /^[a-z][a-z0-9+.-]*:/i.test(raw)) {
            return;
        }
        try {
            const here = pageUrl(), url = new URL(raw, here);
            const from = decodeURIComponent(here.pathname), to = decodeURIComponent(url.pathname);
            if (/\.md$/i.test(to) && to !== from) {
                saveFileJumps(fileJumps().concat({ from, to, time: Date.now() }));
            }
        } catch (e) { /* a link it cannot read: no Back for it */ }
    }

    // The newest jump from another file to this page, when it is newer than this page's own newest jump: its index in
    // <jumps>, else -1
    function fileJumpBack(jumps) {
        const here = decodeURIComponent(pageUrl().pathname), newest = backStack[backStack.length - 1];
        for (let i = jumps.length - 1; i >= 0; i--) {
            if (jumps[i].to === here) {
                return !newest || jumps[i].time > newest.time ? i : -1;
            }
        }
        return -1;
    }

    // Back to the file at <path> (absolute): a link to it, relative to this file, clicked by script. The preview's
    // own click handler takes a link without a scheme whether or not the click is a real one, sends it to the
    // extension and stops the browser from following it; the extension shows that file's preview tab, still where
    // it was, or opens it.
    function openFile(path) {
        const dir = decodeURIComponent(pageUrl().pathname).split('/').slice(0, -1), parts = path.split('/');
        let same = 0;
        while (same < dir.length && same < parts.length - 1 && dir[same] === parts[same]) {
            same++;
        }
        const href = dir.slice(same).map(() => '..').concat(parts.slice(same)).map(encodeURIComponent).join('/');
        const a = document.createElement('a');
        a.id = 'mpp-back-link';
        a.href = href;
        a.dataset.href = href;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    // The editor's Go Back key: ⌃- on the Mac, Ctrl+Alt+- on Linux, Alt+← on Windows; and Ctrl+Alt+← (⌃⌥← on the
    // Mac) everywhere, because Peter's keybindings.json gives Go Back ctrl+alt+left and takes ⌃- away from it.
    function isBackKey(e) {
        if (e.shiftKey || e.metaKey) {
            return false;
        }
        if (e.ctrlKey && e.altKey && e.key === 'ArrowLeft') {
            return true;
        }
        if (IS_MAC) {
            return e.ctrlKey && !e.altKey && e.code === 'Minus';
        }
        if (IS_LINUX) {
            return e.ctrlKey && e.altKey && e.code === 'Minus';
        }
        return e.altKey && !e.ctrlKey && e.key === 'ArrowLeft';
    }

    // a link to a place in this page whose target exists
    function isPageJump(a) {
        const id = a.getAttribute('href').slice(1);
        try {
            return Boolean(id && (document.getElementById(id) || document.getElementById(decodeURIComponent(id))));
        } catch (e) {
            return false;
        }
    }

    // Copy: a button at the top right of every code block, shown while the pointer is over the block
    // (preview.css). It sits in an <mpp-copy> of no height just before the block, not in it: the preview
    // updates its text by comparing each block with the new text, and a block holding a button never
    // matches, which leaves the code's line number (data-line, which scrolling along with the editor and
    // Cmd+double-click go by) out of date. An update drops the <mpp-copy> elements; build() adds them
    // again. The button holds no text: preview.css draws its label from data-state, so the find box, a
    // selection and Cmd+C never pick it up.
    function addCopyButtons(root) {
        for (const code of root.querySelectorAll('pre > code')) {
            const pre = code.parentElement;
            if (pre.previousElementSibling?.localName === 'mpp-copy') {
                continue;
            }
            const button = document.createElement('button');
            button.type = 'button';
            // the preview would act on the click, and open the source on a Cmd+double-click
            button.addEventListener('click', e => {
                e.stopPropagation();
                copyCode(button, code);
            });
            button.addEventListener('dblclick', e => e.stopPropagation());
            const holder = document.createElement('mpp-copy');
            holder.appendChild(button);
            pre.before(holder);
        }
    }

    // The code as written in the file, without the line break that ends its last line, so a pasted
    // command waits for Enter; the label says Copied or Copy failed for 1.5 s.
    async function copyCode(button, code) {
        const text = code.textContent.replace(/\n$/, '');
        let copied;
        try {
            await navigator.clipboard.writeText(text);
            copied = true;
        } catch (e) {
            copied = copyBySelection(text);
        }
        button.dataset.state = copied ? 'copied' : 'failed';
        setTimeout(() => delete button.dataset.state, 1500);
    }

    // Where the webview refuses the clipboard API: the copy command on a selected textarea, which the
    // click allows. preview.css fixes the textarea in the window, so selecting it does not scroll the page.
    function copyBySelection(text) {
        const area = document.createElement('textarea');
        area.id = 'mpp-copy-text';
        area.value = text;
        document.body.appendChild(area);
        area.select();
        const copied = document.execCommand('copy');
        area.remove();
        return copied;
    }

    function build() {
        ensureSidebar();
        ensureFind();
        ensureBack();
        const root = document.querySelector('.markdown-body') || document.body;
        addCopyButtons(root);
        headings = Array.from(root.querySelectorAll(LEVELS));
        links = [];
        list.textContent = '';
        nav.classList.toggle('mpp-empty', headings.length === 0);
        if (headings.length === 0) {
            return;
        }
        const top = Math.min(...headings.map(h => Number(h.tagName[1])));
        for (const h of headings) {
            const a = document.createElement('a');
            a.textContent = h.textContent.trim();
            a.href = '#' + h.id;
            a.className = 'mpp-l' + (Number(h.tagName[1]) - top);
            a.addEventListener('click', e => {
                e.preventDefault();
                e.stopPropagation();
                h.scrollIntoView({ block: 'start' });
            });
            list.appendChild(a);
            links.push(a);
        }
        markCurrent();
    }

    // Highlight the section being read and keep its entry visible in the sidebar.
    function markCurrent() {
        pending = false;
        let current = -1;
        for (let i = 0; i < headings.length && headings[i].getBoundingClientRect().top <= 80; i++) {
            current = i;
        }
        links.forEach((a, i) => a.classList.toggle('mpp-current', i === current));
        const a = links[current];
        if (a && document.body.classList.contains('mpp-on')) {
            const box = nav.getBoundingClientRect();
            const r = a.getBoundingClientRect();
            if (r.top < box.top || r.bottom > box.bottom) {
                nav.scrollTop += r.top - box.top - box.height / 3;
            }
        }
    }

    // Find box at the top right, working like the editor's: Cmd+F (Ctrl+F off the Mac) opens it, Enter
    // and Shift+Enter step through the matches, ↑ / ↓ recall earlier queries, Aa / ab switch match case
    // and whole word (⌥⌘C / ⌥⌘W), Esc closes it from anywhere in the page. Matches are painted with the
    // CSS highlight API, which leaves the page untouched.
    // ↑ ↓ × as 16 px line icons in the text colour, so all three come out the same size whatever the font
    const ICON_PATHS = {
        up: 'M8 13V3M3.5 7.5L8 3l4.5 4.5',
        down: 'M8 3v10M3.5 8.5L8 13l4.5-4.5',
        close: 'M3.5 3.5l9 9M12.5 3.5l-9 9',
    };

    function icon(name) {
        const ns = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');
        svg.setAttribute('viewBox', '0 0 16 16');
        const path = document.createElementNS(ns, 'path');
        path.setAttribute('d', ICON_PATHS[name]);
        svg.appendChild(path);
        return svg;
    }

    function makeFindButton(content, title, onClick) {
        const button = document.createElement('button');
        button.type = 'button';
        button.append(content);
        button.title = title;
        // keep the focus in the input
        button.addEventListener('mousedown', e => e.preventDefault());
        button.addEventListener('click', onClick);
        return button;
    }

    function ensureFind() {
        if (findBox && document.body.contains(findBox)) {
            return;
        }
        try { findHistory = JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; } catch (e) { findHistory = []; }
        try { Object.assign(findOptions, JSON.parse(localStorage.getItem(OPTIONS_KEY))); } catch (e) { /* defaults */ }
        findBox = document.createElement('div');
        findBox.id = 'mpp-find';
        findBox.hidden = true;
        findInput = document.createElement('input');
        findInput.type = 'text';
        findInput.placeholder = 'Find (⇅ for history)';
        const onQuery = () => {
            search(true);
            // as in the editor's find box, a query left for half a second goes into the history
            const query = findInput.value;
            clearTimeout(rememberTimer);
            rememberTimer = setTimeout(() => remember(query), 500);
        };
        // while an input method is composing (typing Chinese), wait for the finished text
        findInput.addEventListener('input', e => {
            if (!e.isComposing) {
                onQuery();
            }
        });
        findInput.addEventListener('compositionend', onQuery);
        optionButtons.matchCase = makeFindButton('Aa', 'Match Case (' + (IS_MAC ? '⌥⌘C' : 'Alt+C') + ')',
            () => toggleFindOption('matchCase'));
        optionButtons.wholeWord = makeFindButton('ab', 'Match Whole Word (' + (IS_MAC ? '⌥⌘W' : 'Alt+W') + ')',
            () => toggleFindOption('wholeWord'));
        optionButtons.wholeWord.id = 'mpp-find-word';
        showFindOptions();
        findCount = document.createElement('span');
        findBox.append(findInput, optionButtons.matchCase, optionButtons.wholeWord, findCount,
            makeFindButton(icon('up'), 'Previous match (Shift+Enter)', () => step(-1)),
            makeFindButton(icon('down'), 'Next match (Enter)', () => step(1)),
            makeFindButton(icon('close'), 'Close (Esc)', closeFind));
        // Enter and the arrow keys are handled here; keep them from reaching the preview's own key
        // handling. Keys that belong to an input method (typing Chinese) are left to it.
        findBox.addEventListener('keydown', e => {
            if (e.isComposing) {
                return;
            }
            if (e.key === 'Enter') {
                step(e.shiftKey ? -1 : 1);
            } else if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && e.target === findInput
                && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
                showHistory(e.key === 'ArrowUp' ? -1 : 1);
            } else {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
        });
        document.body.appendChild(findBox);
    }

    function showFindOptions() {
        for (const [name, button] of Object.entries(optionButtons)) {
            button.setAttribute('aria-pressed', String(findOptions[name]));
        }
    }

    // Aa / ab, kept across previews as the editor keeps them.
    function toggleFindOption(name) {
        findOptions[name] = !findOptions[name];
        try { localStorage.setItem(OPTIONS_KEY, JSON.stringify(findOptions)); } catch (e) { /* this page only */ }
        showFindOptions();
        search(true);
    }

    // ⌥⌘C / ⌥⌘W on the Mac, Alt+C / Alt+W elsewhere, as in the editor's find box.
    function isOptionKey(e, code) {
        return e.code === code && e.altKey && !e.shiftKey && (IS_MAC ? e.metaKey && !e.ctrlKey : !e.metaKey && !e.ctrlKey);
    }

    // Whole word as the editor has it: neither end of the match continues a word, i.e. at each end the
    // character just outside the match or the one at its own edge is a space or a separator.
    function isWordChar(c) {
        return c !== undefined && !/\s/.test(c) && !SEPARATORS.includes(c);
    }

    function isWholeWord(text, start, end) {
        return (!isWordChar(text[start - 1]) || !isWordChar(text[start]))
            && (!isWordChar(text[end]) || !isWordChar(text[end - 1]));
    }

    // Search history, newest last, kept across previews.
    function remember(query) {
        if (!query) {
            return;
        }
        findHistory = findHistory.filter(q => q !== query).concat(query).slice(-50);
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(findHistory)); } catch (e) { /* no storage: this page only */ }
    }

    // ↑ / ↓ in the input: an earlier / a later query; past the newest one the input clears.
    function showHistory(delta) {
        const value = findInput.value;
        if (value && !findHistory.includes(value)) {
            remember(value);
        }
        const next = (value ? findHistory.indexOf(value) : findHistory.length) + delta;
        if (next >= 0) {
            findInput.value = findHistory[next] || '';
            search(true);
        }
    }

    function openFind() {
        const selected = String(window.getSelection()).trim();
        if (selected && !selected.includes('\n')) {
            findInput.value = selected;
        }
        findBox.hidden = false;
        findInput.focus();
        findInput.select();
        search(true);
    }

    function closeFind() {
        findBox.hidden = true;
        matches = [];
        if (CAN_HIGHLIGHT) {
            CSS.highlights.delete('mpp-match');
            CSS.highlights.delete('mpp-match-current');
        }
    }

    // All matches of the query under the Aa / ab options. The page text is searched as one string, so a
    // match may run across links, inline code and syntax colouring; starts[i] is where nodes[i] begins.
    function search(scroll) {
        matches = [];
        if (findInput.value) {
            const root = document.querySelector('.markdown-body') || document.body;
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
            const nodes = [], starts = [];
            let text = '';
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                nodes.push(node);
                starts.push(text.length);
                text += node.data;
            }
            const query = new RegExp(findInput.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
                findOptions.matchCase ? 'g' : 'gi');
            let first = 0;
            for (const m of text.matchAll(query)) {
                const end = m.index + m[0].length;
                if (findOptions.wholeWord && !isWholeWord(text, m.index, end)) {
                    continue;
                }
                while (starts[first + 1] <= m.index) {
                    first++;
                }
                let last = first;
                while (starts[last + 1] < end) {
                    last++;
                }
                const range = new Range();
                range.setStart(nodes[first], m.index - starts[first]);
                range.setEnd(nodes[last], end - starts[last]);
                matches.push(range);
            }
        }
        // start from the first match at or below the top of the window
        matchIndex = Math.max(0, matches.findIndex(r => r.getBoundingClientRect().top >= 0));
        showMatches(scroll);
    }

    function step(delta) {
        if (matches.length > 0) {
            matchIndex = (matchIndex + delta + matches.length) % matches.length;
            showMatches(true);
        }
    }

    function showMatches(scroll) {
        const count = matches.length;
        // as in the editor's find box, also "No results" while the input is empty
        findCount.textContent = count > 0 ? (matchIndex + 1) + ' of ' + count : 'No results';
        const range = matches[matchIndex];
        if (CAN_HIGHLIGHT) {
            const all = new Highlight();
            const current = new Highlight();
            matches.forEach(r => all.add(r));
            if (range) {
                current.add(range);
            }
            current.priority = 1;
            CSS.highlights.set('mpp-match', all);
            CSS.highlights.set('mpp-match-current', current);
        }
        if (scroll && range) {
            const box = range.getBoundingClientRect();
            if (box.top < 0 || box.bottom > window.innerHeight) {
                window.scrollBy(0, box.top - window.innerHeight / 3);
            }
        }
    }

    // The preview loads this script async and puts the first text into the page without firing
    // vscode.markdown.updateContent, so rebuild whenever the page content changes, once per frame.
    let buildQueued = false;
    function queueBuild() {
        if (!buildQueued) {
            buildQueued = true;
            requestAnimationFrame(() => {
                buildQueued = false;
                build();
                if (!findBox.hidden) {
                    search(false);
                }
            });
        }
    }

    function isOwnNode(node) {
        const element = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        return Boolean(element && element.closest(OWN));
    }

    function onMutations(mutations) {
        const fromPage = mutations.some(m => !isOwnNode(m.target)
            && [...m.addedNodes, ...m.removedNodes].some(n => !isOwnNode(n)));
        if (fromPage) {
            queueBuild();
        }
    }

    // Where a link points: a web link as written; a link to a file as the file's absolute path, with any
    // ?v=<commit> and #fragment, resolved against this document the way the preview resolves it.
    function linkAddress(a) {
        const raw = a.getAttribute('data-href') || a.getAttribute('href');
        if (/^[a-z][a-z0-9+.-]*:/i.test(raw) && !/^file:/i.test(raw)) {
            return raw;
        }
        try {
            const settings = document.getElementById('vscode-markdown-preview-data').getAttribute('data-settings');
            const url = new URL(raw, JSON.parse(settings).source);
            return decodeURIComponent(url.pathname + url.search + url.hash);
        } catch (e) {
            return raw;
        }
    }

    function init() {
        // A double click opens the source only with Cmd held; a plain double click stays in the preview.
        // The preview's own handler listens on document, so stop the event before it gets there.
        window.addEventListener('dblclick', e => {
            if (!e.metaKey) {
                e.stopPropagation();
            }
        }, true);
        // Find keys from anywhere in the page: Cmd+F opens the find box; while it is open, Esc closes it
        // and ⌥⌘C / ⌥⌘W switch Aa / ab. After a jump inside the page, or from another file's page, the Go
        // Back key returns. Stop them here: the preview would otherwise pass them on to Cursor. With nothing
        // to go back to, Go Back goes on to Cursor.
        window.addEventListener('keydown', e => {
            if (e.isComposing) {
                return;
            }
            if (e[FIND_MOD] && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'f') {
                openFind();
            } else if (e.key === 'Escape' && !findBox.hidden) {
                closeFind();
            } else if (isOptionKey(e, 'KeyC') && !findBox.hidden) {
                toggleFindOption('matchCase');
            } else if (isOptionKey(e, 'KeyW') && !findBox.hidden) {
                toggleFindOption('wholeWord');
            } else if (isBackKey(e) && canGoBack()) {
                goBack();
            } else {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
        }, true);
        // A left click on a link to a place in this page, a sidebar entry included, with or without Cmd, Shift
        // and the like held (the page jumps either way): remember where the page was before the webview (or
        // the sidebar) scrolls to the target.
        window.addEventListener('click', e => {
            const a = e.target instanceof Element ? e.target.closest('a[href^="#"]') : null;
            if (a && e.button === 0 && isPageJump(a)) {
                rememberPosition();
            }
        }, true);
        // A left click, with or without Cmd and the like, on a link to another .md file: remember the jump for the
        // Back of that file's page. Only a real click: the one goBack makes to return to another file is not a jump.
        window.addEventListener('click', e => {
            const a = e.target instanceof Element ? e.target.closest('a[href]') : null;
            if (a && e.button === 0 && e.isTrusted) {
                rememberFileJump(a);
            }
        }, true);
        // another page's jump to this one, or back from it, changes whether there is something to go back to
        window.addEventListener('storage', e => {
            if (e.key === JUMPS_KEY) {
                updateBack();
            }
        });
        document.addEventListener('visibilitychange', updateBack);
        // Right click on a link, in the text or in the sidebar: the webview's own Cut / Copy / Paste act on the
        // selection only, so on a link they do nothing. Give the menu the link instead: Copy Link Address, Copy
        // Link Text, and Copy when text is selected (package.json, extension.js); a sidebar entry's address is
        // this file with the heading's #anchor. The menu elsewhere stays as it is.
        window.addEventListener('contextmenu', e => {
            const a = e.target instanceof Element ? e.target.closest('a[href]') : null;
            if (!a) {
                return;
            }
            a.dataset.vscodeContext = JSON.stringify({
                webviewSection: 'mppLink',
                preventDefaultContextMenuItems: true,
                mppHref: linkAddress(a),
                mppText: a.textContent.trim(),
                mppSelection: String(document.getSelection() || ''),
            });
        }, true);
        build();
        new MutationObserver(onMutations).observe(document.body, { childList: true, subtree: true });
        window.addEventListener('vscode.markdown.updateContent', queueBuild);
        window.addEventListener('scroll', () => {
            if (!pending) {
                pending = true;
                requestAnimationFrame(markCurrent);
            }
        }, { passive: true });
    }

    if (document.body) {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
