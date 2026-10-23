(function () {
  // The engine's stage script: playback, transport and keyboard, the caption, one row per function with its HCA stage
  // chip, the command tokens between host and device, the pass or fail banner, the run map playhead, and keeping the
  // stage and the document in step. The story's script (window.WALK_STORY, loaded before this one) draws its device side
  // through three optional hooks: init(api) once, chipTags(choreo, stages) and apply(index, choreo, prev, api) per step.
  const D = JSON.parse(document.getElementById('walk-data').textContent);
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const steps = Array.from(document.querySelectorAll('article.step'));
  const N = steps.length;
  const $ = (id) => document.getElementById(id);
  const svgNS = 'http://www.w3.org/2000/svg';
  // the rows the engine drew: function name and the y of its rail
  const lanes = Array.from(document.querySelectorAll('.scene .fnrow')).map((g) => ({ fn: g.dataset.fn, y: +g.dataset.y }));
  const rowY = {};
  lanes.forEach((l) => { rowY[l.fn] = l.y; });
  let cur = -1, playing = false, timer = null, speed = 1, anims = [], cues = [], programmatic = false, progTimer = null;

  function el(tag, attrs, parent) {
    const e = document.createElementNS(svgNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function textW(s) { return Math.max(40, s.length * 6.7 + 18); }
  function perCmd(cmds) { return cmds.length > 2 ? 900 : 1300; }
  // what the story's script may use; it hands its animations to track() so the next step cancels them
  const api = { D, $, el, reduce, perCmd, track: (a) => { anims.push(a); return a; } };
  const story = window.WALK_STORY || {};
  if (story.init) story.init(api);

  // tags: function -> a word added to its chip (the story's, such as WA for a step a local workaround made)
  function setChips(stage, changed, tags) {
    for (const { fn } of lanes) {
      const t = $('chip-' + fn.toLowerCase());
      const bg = $('chipbg-' + fn.toLowerCase());
      let label = stage[fn] || 'DISABLED_HCA';
      if (tags[fn]) label += ' · ' + tags[fn];
      t.textContent = label;
      // the longest names (MODIFY_NIC_VPORT_CONTEXT) are squeezed to fit the chip instead of spilling out of it
      if (label.length > 18) { t.setAttribute('textLength', 118); t.setAttribute('lengthAdjust', 'spacingAndGlyphs'); }
      else { t.removeAttribute('textLength'); t.removeAttribute('lengthAdjust'); }
      bg.classList.toggle('tag', !!tags[fn]);
      if (changed.includes(fn) && !reduce) {
        bg.classList.add('flash');
        setTimeout(() => bg.classList.remove('flash'), 900);
      }
    }
  }
  function clearTokens() {
    anims.forEach((a) => { try { a.cancel(); } catch (e) {} });
    anims = [];
    cues.forEach(clearTimeout);
    cues = [];
    const g = $('tokens');
    while (g.firstChild) g.removeChild(g.firstChild);
  }
  function token(cls, fn, label, y, from, to, delay, dur) {
    const g = el('g', { class: 'tok ' + cls + ' ' + fn.toLowerCase() }, $('tokens'));
    const w = textW(label);
    el('rect', { x: -w / 2, y: -11, width: w, height: 22, rx: 11 }, g);
    const t = el('text', { x: 0, y: 4, 'text-anchor': 'middle' }, g);
    t.textContent = label;
    if (reduce) { g.setAttribute('transform', 'translate(' + to + ',' + y + ')'); return g; }
    g.style.opacity = 0;
    const a = g.animate([
      { transform: 'translate(' + from + 'px,' + y + 'px)', opacity: 0 },
      { transform: 'translate(' + (from + (to - from) * 0.15) + 'px,' + y + 'px)', opacity: 1, offset: 0.15 },
      { transform: 'translate(' + to + 'px,' + y + 'px)', opacity: 1 }
    ], { duration: dur, delay: delay, easing: 'cubic-bezier(.3,.7,.3,1)', fill: 'forwards' });
    anims.push(a);
    return g;
  }
  // Each command: the request travels host -> device, then the reply travels back and stays (the last one) or fades.
  // par: all commands go out together (two functions at once), and every reply stays. onSend(i) runs as command i goes out.
  function playCmds(cmds, par, onSend) {
    const per = perCmd(cmds);
    cmds.forEach((c, i) => {
      const [fn, req, rep, kind] = c;
      const y = rowY[fn];
      if (y === undefined) return;
      const last = par || i === cmds.length - 1;
      const repW = textW(rep);
      if (reduce) {
        if (last) token('rep ' + kind, fn, rep, y, 0, 300 + repW / 2 + 4, 0, 0);
        return;
      }
      const base = par ? 0 : i * per;
      if (onSend) cues.push(setTimeout(() => onSend(i), base));
      const reqW = textW(req);
      const r = token('req', fn, req, y, 300 + reqW / 2, 652 - reqW / 2 - 4, base, per * 0.55);
      anims.push(r.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 200, delay: base + per * 0.55, fill: 'forwards' }));
      const p = token('rep ' + kind, fn, rep, y, 652 - repW / 2 - 4, 300 + repW / 2 + 4, base + per * 0.55, per * 0.5);
      if (!last) anims.push(p.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 250, delay: base + per * 1.08, fill: 'forwards' }));
    });
    return (par ? 1 : cmds.length) * per;
  }

  // transport
  const dotEls = Array.from(document.querySelectorAll('.dot'));
  const playBtn = $('t-play');
  function setPlayIcon() {
    playBtn.innerHTML = playing ? '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2h3v12H4zM9 2h3v12H9z"/></svg>' : '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>';
    playBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
  }
  function stageHeight() {
    const s = document.querySelector('.stage-wrap');
    const sticky = getComputedStyle(s).position === 'sticky';
    document.documentElement.style.setProperty('--stage-h', (sticky ? s.offsetHeight + 12 : 16) + 'px');
  }
  function go(i, opts) {
    opts = opts || {};
    i = Math.max(0, Math.min(N - 1, i));
    const prev = cur;
    cur = i;
    const m = D.steps[i];
    const c = D.choreo[m.id] || {};
    clearTokens();
    steps.forEach((s, k) => s.classList.toggle('current', k === i));
    dotEls.forEach((d, k) => { d.classList.toggle('cur', k === i); d.classList.toggle('done', k < i); d.setAttribute('aria-current', k === i ? 'step' : 'false'); });
    document.querySelectorAll('.fseg').forEach((f) => f.classList.toggle('on', +f.dataset.flow === m.flow));
    $('cap-n').textContent = 'Step ' + (i + 1) + ' / ' + N;
    $('cap-t').textContent = m.title;
    $('cap-s').textContent = D.say[m.id] || '';
    $('stepcount').textContent = 'Flow ' + m.flow + ' · L' + m.first.toLocaleString('en-US') + ' · ' + m.time;
    // The chips: the stages before the step's first command, then each command moves them as it goes out (utopx changes
    // its model of a function when it sends). With reduced motion, or when no command has a log line: the step's end.
    let shown = prev >= 0 ? D.stages[prev] : null;
    const chipsTo = (st) => {
      const changed = lanes.filter(({ fn }) => !shown || shown[fn] !== st[fn]).map(({ fn }) => fn);
      setChips(st, changed, story.chipTags ? story.chipTags(c, st) : {});
      shown = st;
    };
    const seq = reduce ? null : (D.chips || {})[m.id];
    chipsTo(seq ? seq[0] : D.stages[i]);
    if (story.apply) story.apply(i, c, prev, api);
    $('banner').classList.toggle('show', !!c.passed || c.banner === 'fail');
    const ph = $('playhead');
    if (ph) ph.setAttribute('transform', 'translate(' + D.mapX[i] + ',0)');
    const dur = playCmds(c.cmds || [], c.par, seq ? (k) => { if (seq[k + 1]) chipsTo(seq[k + 1]); } : null);
    if (!opts.noScroll) scrollToStep(i, opts.instant);
    if (playing) schedule(dur);
  }
  // While the page scrolls to a step on its own, steps passing the middle of the screen must not take the stage.
  function scrollToStep(i, instant) {
    programmatic = true;
    clearTimeout(progTimer);
    progTimer = setTimeout(() => { programmatic = false; }, 3000);
    steps[i].scrollIntoView({ behavior: (reduce || instant) ? 'auto' : 'smooth', block: 'start' });
  }
  window.addEventListener('scrollend', () => {
    if (!programmatic) return;
    clearTimeout(progTimer);
    progTimer = setTimeout(() => { programmatic = false; }, 150);
  });
  function schedule(dur) {
    clearTimeout(timer);
    const read = Math.max(5200, dur + 3800) / speed;
    const fill = dotEls[cur] && dotEls[cur].querySelector('.fill');
    if (fill && !reduce) { fill.getAnimations().forEach((a) => a.cancel()); fill.animate([{ width: '0%' }, { width: '100%' }], { duration: read, fill: 'forwards' }); }
    timer = setTimeout(() => { if (cur >= N - 1) { playing = false; setPlayIcon(); return; } go(cur + 1); }, read);
  }
  function play(on) {
    playing = on;
    setPlayIcon();
    clearTimeout(timer);
    if (on) { if (cur >= N - 1) go(0); else go(cur < 0 ? 0 : cur); }
  }
  playBtn.addEventListener('click', () => play(!playing));
  $('t-prev').addEventListener('click', () => { play(false); go(cur - 1); });
  $('t-next').addEventListener('click', () => { play(false); go(cur + 1); });
  $('t-speed').addEventListener('click', (e) => { speed = speed === 1 ? 2 : 1; e.currentTarget.textContent = speed + '×'; if (playing) schedule(0); });
  $('t-mini').addEventListener('click', (e) => { const s = document.querySelector('.stage'); s.classList.toggle('mini'); e.currentTarget.setAttribute('aria-pressed', s.classList.contains('mini')); e.currentTarget.textContent = s.classList.contains('mini') ? 'Show stage' : 'Hide stage'; stageHeight(); });
  dotEls.forEach((d, k) => d.addEventListener('click', () => { play(false); go(k); }));
  document.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', (e) => { e.preventDefault(); const k = +b.dataset.go; if (b.classList.contains('play-here')) { playing = true; setPlayIcon(); go(k); } else { play(false); go(k); } }));
  document.addEventListener('keydown', (e) => {
    if (e.target.closest('input, textarea, select, summary, a')) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); play(false); go(cur + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); play(false); go(cur - 1); }
    else if (e.key === ' ') { if (e.target.closest('button')) return; e.preventDefault(); play(!playing); }
  });
  // scrolling the document moves the stage too
  const io = new IntersectionObserver((entries) => {
    if (programmatic) return;
    let best = null;
    entries.forEach((en) => { if (en.isIntersecting && (!best || en.boundingClientRect.top < best.boundingClientRect.top)) best = en; });
    if (best) {
      const k = steps.indexOf(best.target);
      if (k !== cur) { if (playing) play(false); go(k, { noScroll: true }); }
    }
  }, { rootMargin: '-45% 0px -50% 0px' });
  steps.forEach((s) => io.observe(s));
  window.addEventListener('resize', stageHeight);
  stageHeight();
  setPlayIcon();
  // a link to the page with #<step id> opens that step
  const fromHash = D.steps.findIndex((m) => '#' + m.id === location.hash);
  if (fromHash > 0) { go(fromHash, { instant: true }); } else { go(0, { noScroll: true }); }
})();
