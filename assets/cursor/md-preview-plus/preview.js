// Built-in Markdown preview: a heading sidebar on the left, rebuilt whenever the text changes, and a
// find box, since Cursor's own find does not work in the preview. The preview keeps the rendered
// text in .markdown-body; the sidebar and the find box live outside it, so the preview's updates
// leave them in place.
(function () {
    'use strict';
    const HIDDEN_KEY = 'md-preview-plus-sidebar-hidden';
    const WIDTH_KEY = 'md-preview-plus-sidebar-width';
    const HISTORY_KEY = 'md-preview-plus-find-history';
    const OPTIONS_KEY = 'md-preview-plus-find-options';
    const LEVELS = 'h1, h2, h3, h4';
    // our own nodes; changes inside them are not changes of the page
    const OWN = '#mpp-sidebar, #mpp-toggle, #mpp-resize, #mpp-find';
    const IS_MAC = /Mac/.test(navigator.platform);
    const FIND_MOD = IS_MAC ? 'metaKey' : 'ctrlKey';
    const CAN_HIGHLIGHT = Boolean(window.Highlight && window.CSS && CSS.highlights);
    // the editor's default word separators, for "match whole word"
    const SEPARATORS = '`~!@#$%^&*()-=+[{]}\\|;:\'",.<>/?';
    let nav, list, headings = [], links = [], pending = false;
    let findBox, findInput, findCount, matches = [], matchIndex = 0, findHistory = [], rememberTimer;
    let findOptions = { matchCase: false, wholeWord: false }, optionButtons = {};

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

    function build() {
        ensureSidebar();
        ensureFind();
        const root = document.querySelector('.markdown-body') || document.body;
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
            a.textContent = a.title = h.textContent.trim();
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

    function init() {
        // A double click opens the source only with Cmd held; a plain double click stays in the preview.
        // The preview's own handler listens on document, so stop the event before it gets there.
        window.addEventListener('dblclick', e => {
            if (!e.metaKey) {
                e.stopPropagation();
            }
        }, true);
        // Find keys from anywhere in the page: Cmd+F opens the find box; while it is open, Esc closes it
        // and ⌥⌘C / ⌥⌘W switch Aa / ab. Stop them here: the preview would otherwise pass them on to Cursor.
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
            } else {
                return;
            }
            e.preventDefault();
            e.stopPropagation();
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
