window.WALK_STORY = (function () {
  // The PSF story's device side of the stage: the global-mode lamp, the PSF pool filling range by range, the PF ICM fed
  // from it, the udriver scene (step psf-udriver) and the run counters (step no-page-request). Choreography keys used
  // here: glob, pool, feed, gone, wa, scene. The engine's stage script calls init once and chipTags and apply per step.
  let segs = [], v1rects = [], itRects = [];
  const GLOB = { off: 'not set', offered: 'offered by FW in QUERY_PAGES', on: 'on: requested with the first range',
                 confirmed: 'on: caps read page_request_disable = 1', cleared: 'cleared by REGULAR TEARDOWN_HCA (FW code)' };

  function init(api) {
    const { D, $, el } = api;
    // pool segments, to scale
    const segG = $('poolsegs');
    const total = D.sizes.reduce((a, b) => a + b, 0);
    let x = 668;
    segs = D.sizes.map((s, i) => {
      const w = 312 * s / total;
      const r = el('rect', { class: 'pseg', x: x.toFixed(1), y: 113, width: Math.max(1, w - 0.5).toFixed(1), height: 28 }, segG);
      el('title', {}, r).textContent = 'R' + (i + 1) + ': ' + s.toLocaleString('en-US') + ' pages, ' + (s * 4096 / 1048576).toFixed(1) + ' MiB, IOVA ' + D.addr[i][0] + ' – ' + D.addr[i][1];
      // a label only where it fits: number and size from 48 units, the number alone from 18
      const t = w > 18 ? el('text', { class: 'pseg-l', x: (x + (w > 48 ? 6 : 4)).toFixed(1), y: 131 }, segG) : null;
      if (t) t.textContent = 'R' + (i + 1) + (w > 48 ? ' · ' + Math.round(s * 4096 / 1048576) + ' MiB' : '');
      r.style.transform = 'scaleX(0)';
      if (t) t.style.opacity = 0;
      x += w;
      return { r, t };
    });
    // udriver scene: host pages and the old call's windows
    const pg = $('ud-pages');
    for (let i = 0; i < 64; i++) el('rect', { class: 'ud-page', x: 318 + (i % 32) * 20.5, y: 56 + Math.floor(i / 32) * 22, width: 17, height: 17, rx: 2 }, pg);
    const v1 = $('ud-v1');
    // The old call: 1024 pages per request, only the last one shorter. Each window lands where the IOMMU puts it, so the
    // gaps vary; none touches the next.
    const J = [0, 5, 2, 7, 1, 6, 3], tail = D.sizes[0] % 1024 || 1024;
    for (let i = 0; i < 20; i++) v1rects.push(el('rect', { class: 'ud-chunk', x: 318 + i * 30 + J[i % 7], y: 138, width: 20, height: 18, rx: 3 }, v1));
    el('text', { class: 'ud-sub', x: 928, y: 151, 'text-anchor': 'middle' }, v1).textContent = '⋯';
    v1rects.push(el('rect', { class: 'ud-chunk', x: 942, y: 138, width: 20 * tail / 1024, height: 18, rx: 3 }, v1));
    el('text', { class: 'ud-sub', x: 328, y: 169, 'text-anchor': 'middle' }, v1).textContent = '1024';
    el('text', { class: 'ud-sub', x: 942 + 10 * tail / 1024, y: 169, 'text-anchor': 'middle' }, v1).textContent = String(tail);
    // run scene: one tick per iteration
    const iters = $('rs-iters');
    for (let i = 0; i < D.iters; i++) itRects.push(el('rect', { class: 'rs-tick', x: 330 + i * 630 / Math.max(D.iters, 50), y: 150, width: Math.max(2, 9 * 50 / Math.max(D.iters, 50)), height: 40, rx: 2, opacity: 0.15 }, iters));
  }

  // from: segments already shown before this step; they stay. New ones grow in as each range's reply comes back.
  function setPool(api, n, from, per) {
    const { D, $ } = api;
    segs.forEach((s, i) => {
      const on = i < n;
      s.r.style.transform = on ? 'scaleX(1)' : 'scaleX(0)';
      if (s.t) s.t.style.opacity = on ? 1 : 0;
      if (on && i >= from && !api.reduce) {
        const delay = (i - from) * per + per * 0.6;
        api.track(s.r.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 650, delay: delay, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards' }));
        if (s.t) api.track(s.t.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: delay + 500, fill: 'backwards' }));
      }
    });
    const pages = D.sizes.slice(0, n).reduce((a, b) => a + b, 0);
    $('pool-v').textContent = n ? pages.toLocaleString('en-US') + ' × 4 KiB pages · ' + (pages * 4096 / 1073741824).toFixed(2) + ' GiB' : 'empty';
  }
  function setGlob(api, g) {
    const e = api.$('glob');
    e.setAttribute('class', 'glob ' + g);
    api.$('glob-v').textContent = GLOB[g];
  }
  function udScene(api, show) {
    const { $ } = api;
    $('udscene').classList.toggle('show', show);
    if (!show) return;
    const bar = $('ud-v2bar');
    if (api.reduce) { bar.style.transform = 'scaleX(1)'; v1rects.forEach((r) => r.style.opacity = 1); return; }
    v1rects.forEach((r, i) => api.track(r.animate([{ opacity: 0, transform: 'translateY(-30px)' }, { opacity: 1, transform: 'none' }], { duration: 300, delay: 200 + i * 45, fill: 'both' })));
    api.track(bar.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 1100, delay: 1500, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'both' }));
  }
  function runScene(api, show) {
    const { D, $ } = api;
    $('runscene').classList.toggle('show', show);
    if (!show) return;
    const T = api.reduce ? 0 : 2600;
    const t0 = performance.now();
    const goal = { cmd: D.pfCmds, ev: D.events };
    function frame(now) {
      const k = T ? Math.min(1, (now - t0) / T) : 1;
      const e = 1 - Math.pow(1 - k, 3);
      $('rs-cmd').textContent = Math.round(goal.cmd * e).toLocaleString('en-US');
      $('rs-ev').textContent = Math.round(goal.ev * e).toLocaleString('en-US');
      const it = Math.round(D.iters * e);
      $('rs-it').textContent = 'iteration ' + it + ' / ' + D.iters + ' · page-request check each iteration';
      itRects.forEach((r, i) => r.setAttribute('opacity', i < it ? 0.9 : 0.15));
      if (k < 1 && $('runscene').classList.contains('show')) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // a step a local workaround produced shows WA on the PSF's chip
  function chipTags(c, stage) {
    const tags = {};
    if (c.wa && stage[c.wa] === 'DISABLED_HCA') tags[c.wa] = 'WA';
    return tags;
  }
  function apply(i, c, prev, api) {
    const { D, $ } = api;
    setGlob(api, c.glob || 'off');
    const prevPool = prev >= 0 ? ((D.choreo[D.steps[prev].id] || {}).pool || 0) : (c.pool || 0);
    setPool(api, c.pool || 0, Math.min(prevPool, c.pool || 0), api.perCmd(c.cmds || []));
    $('pool-gone').classList.toggle('show', !!c.gone);
    // Small ranges are too narrow for a label in the bar, so the sizes are listed under it.
    const legend = (n) => n === 1 ? 'R1 ' + Math.round(D.sizes[0] * 4096 / 1048576) + ' MiB, starting at ' + D.addr[0][0]
      : D.sizes.slice(0, n).map((s, k) => 'R' + (k + 1) + ' ' + Math.round(s * 4096 / 1048576)).join(' · ') + ' MiB';
    $('pool-note').textContent = c.gone ? 'REGULAR TEARDOWN_HCA takes the pool back (FW code)'
      : (c.feed ? '' : 'Each range: one contiguous IOVA block, one MANAGE_PAGES');
    $('pool-note2').textContent = c.gone ? 'psf_pool_handle_teardown_hca_reclaim()'
      : (c.feed || !(c.pool > 0) ? '' : legend(c.pool));
    $('feed').classList.toggle('show', !!c.feed);
    udScene(api, c.scene === 'udriver');
    runScene(api, c.scene === 'run');
  }
  return { init, chipTags, apply };
})();
