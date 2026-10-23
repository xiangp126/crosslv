"""PSF story: the device side of the stage (global-mode lamp, pool, PF ICM, udriver and run overlays) and the
udriver figure and explainer of step psf-udriver."""
from wt.fmt import GERRIT_AUTOMATION, GERRIT_UDRIVER, GERRIT_UTOPX


def split(u, sep=' × 1024 + 1 × '):
    """The old call's chunks: '241 × 1024 + 1 × 828', or '242 × 1024' when the last one is full."""
    return '%d%s%d' % (u['chunks'] - 1, sep, u['tail']) if u['tail'] != 1024 else '%d × 1024' % u['chunks']


def udriver_figure(u):
    """Before/after diagram of the udriver mapping path: utopx -> udriver library -> netlink -> kernel module -> IOMMU -> FW."""
    def box(x, y, w, h, lines):
        out = ['<rect class="udf-box" x="%d" y="%d" width="%d" height="%d" rx="8"/>' % (x, y, w, h)]
        for ty, cls, txt in lines:
            out.append('<text class="%s" x="%d" y="%d" text-anchor="middle">%s</text>' % (cls, x + w // 2, ty, txt))
        return ''.join(out)
    p = ['<svg class="udfig" viewBox="0 0 1000 392" role="img" aria-labelledby="udf-title">'
         '<title id="udf-title">How udriver maps the first range: the old call and the new single-chunk call</title>'
         '<defs>'
         '<marker id="udf-a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" class="udf-ah"/></marker>'
         '<marker id="udf-a-bad" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" class="udf-ah bad"/></marker>'
         '<marker id="udf-a-ok" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L8 4L0 8z" class="udf-ah ok"/></marker>'
         '</defs>']
    for x, t in ((81, 'UTOPX'), (250, 'UDRIVER LIBRARY · USER SPACE'), (379, 'NETLINK'), (510, 'UDRIVER KERNEL MODULE'),
                 (734, 'IOMMU → DEVICE ADDRESSES (IOVA)'), (925, 'FW')):
        p.append('<text class="udf-col" x="%d" y="16" text-anchor="middle">%s</text>' % (x, t))
    # lanes
    # The two lanes differ by the call, not by the udriver version: 3.09 still chunks when the old call is used.
    p.append('<rect class="udf-lane bad" x="8" y="50" width="984" height="140" rx="10"/>'
             '<text class="udf-row bad" x="20" y="40">Old call · udriver_dma_map(ctx, mem, memlen, &amp;dma) · 1024 pages per request, still the same in 3.09</text>'
             '<text class="udf-foot" x="20" y="208">#22 took this path: utopx once mapped range 1 with the old call, because it set the global flag only after '
             'allocating (#21). v2 already existed then. %s</text>'
             '<g transform="translate(0 20)">'
             '<rect class="udf-lane ok" x="8" y="222" width="984" height="140" rx="10"/>'
             '<text class="udf-row ok" x="20" y="212">New call · udriver_dma_map_v2(ctx, mem, memlen, single_chunk_mapping = 1, &amp;dma) · new in 3.09</text>' % (
                 'This run used v2.' if u['contiguous'] else 'In this run the first range is not one window.'))
    # ---- before ----
    buf, pages = '%.0f MiB buffer' % u['mib'], '%s pages' % f'{u["pages"]:,}'
    p.append(box(22, 80, 118, 78, [(104, 'udf-t', 'DmaDesc'), (123, 'udf-s', buf), (140, 'udf-s', pages)]))
    p.append('<path class="udf-ar" d="M141 119 H166" marker-end="url(#udf-a)"/>')
    # 247,612 pages = 241 chunks of 1024 + one of 828: equal blocks, a gap, the last one shorter
    p.append(box(170, 64, 160, 112, [(84, 'udf-t', 'cut into chunks'), (146, 'udf-s', split(u)),
                                     (164, 'udf-s', 'before 3.09: int memlen')]))
    for i, (x, y) in enumerate([(184 + c * 23, 96) for c in range(6)] + [(184 + c * 23, 116) for c in range(4)]):
        p.append('<rect class="udf-chunk pop" style="animation-delay:%.2fs" x="%d" y="%d" width="18" height="14" rx="2"/>' % (0.08 * i, x, y))
    p.append('<text class="udf-s" x="281" y="127" text-anchor="middle">⋯</text>'
             '<rect class="udf-chunk pop" style="animation-delay:0.88s" x="299" y="116" width="%.1f" height="14" rx="2"/>' % (18 * u['tail'] / 1024))
    for k, y in enumerate((80, 100, 120, 140, 160)):
        p.append('<path class="udf-ar bad flow" style="animation-delay:%.2fs" d="M333 %d H426" marker-end="url(#udf-a-bad)"/>' % (0.15 * k, y))
    p.append('<text class="udf-lab bad" x="379" y="62" text-anchor="middle">%d requests</text>' % u['chunks'])
    p.append(box(430, 64, 160, 112, [(84, 'udf-t', 'pin + dma_map_sg'), (102, 'udf-s', 'once per request'),
                                     (124, 'udf-s', 'before 3.09:'), (140, 'udf-s', 'reply sized per page'),
                                     (158, 'udf-s', '32-bit segment length')]))
    p.append('<path class="udf-ar" d="M592 119 H612" marker-end="url(#udf-a)"/>')
    p.append('<line class="udf-axis" x1="618" x2="852" y1="130" y2="130"/>')
    # one window per request: 1024 pages each, the last 828; they land wherever the IOMMU puts them, so the gaps vary
    for k, x in enumerate((620, 650, 684, 712, 744, 774)):
        p.append('<rect class="udf-win bad pop" style="animation-delay:%.2fs" x="%d" y="110" width="20" height="18" rx="2"/>' % (0.1 * k + 0.4, x))
    p.append('<text class="udf-s" x="806" y="124" text-anchor="middle">⋯</text>'
             '<rect class="udf-win bad pop" style="animation-delay:1.0s" x="820" y="110" width="%.1f" height="18" rx="2"/>' % (20 * u['tail'] / 1024))
    p.append('<text class="udf-s" x="630" y="104" text-anchor="middle">1024</text>'
             '<text class="udf-s" x="828" y="104" text-anchor="middle">%d</text>'
             '<text class="udf-lab bad" x="735" y="150" text-anchor="middle">%d windows: %s</text>'
             '<text class="udf-lab bad" x="735" y="165" text-anchor="middle">nothing makes them touch</text>' % (
                 u['tail'], u['chunks'], split(u, ' × 1024 pages + 1 × ')))
    p.append('<path class="udf-ar bad dash" d="M864 98 C 800 70, 690 74, 646 106" marker-end="url(#udf-a-bad)"/>'
             '<text class="udf-x" x="645" y="124" text-anchor="middle">✗</text>')
    p.append(box(866, 64, 118, 112, [(84, 'udf-t', 'FW'), (102, 'udf-s', 'PAS[0] + N pages'), (120, 'udf-s', 'first + k × 4K'),
                                     (142, 'udf-bad', 'lands in a gap'), (160, 'udf-s', '#22 · 0x9BAE1A')]))
    # ---- after ----
    p.append(box(22, 252, 118, 78, [(276, 'udf-t', 'DmaDesc'), (295, 'udf-s', buf), (312, 'udf-s', pages)]))
    p.append('<path class="udf-ar" d="M141 291 H166" marker-end="url(#udf-a)"/>')
    p.append(box(170, 236, 160, 112, [(256, 'udf-t', 'one chunk'), (318, 'udf-s', 'single_chunk_mapping = 1'),
                                      (336, 'udf-s', 'uint64_t memlen')]))
    p.append('<rect class="udf-one grow" x="184" y="268" width="132" height="32" rx="3"/>'
             '<text class="udf-in" x="250" y="289" text-anchor="middle">%s</text>' % pages)
    p.append('<path class="udf-ar ok thick flow" d="M333 291 H424" marker-end="url(#udf-a-ok)"/>'
             '<text class="udf-lab ok" x="379" y="276" text-anchor="middle">1 request</text>')
    p.append(box(430, 236, 160, 112, [(256, 'udf-t', 'pin + one dma_map_sg'), (274, 'udf-s', 'whole scatter list'),
                                      (302, 'udf-s', 'reply per merged segment'), (320, 'udf-s', '64-bit · mapped entries'),
                                      (338, 'udf-s', '1428108 · 1452727')]))
    p.append('<path class="udf-ar" d="M592 291 H612" marker-end="url(#udf-a)"/>')
    p.append('<line class="udf-axis" x1="618" x2="852" y1="302" y2="302"/>'
             '<rect class="udf-win ok grow" x="620" y="282" width="230" height="18" rx="2"/>'
             '<text class="udf-s" x="620" y="320">%s</text><text class="udf-s" x="850" y="320" text-anchor="end">%s + 4K</text>'
             '<text class="udf-lab ok" x="735" y="340" text-anchor="middle">one window · the IOMMU maps it contiguous</text>' % (
                 u['first'], u['last']))
    p.append(box(866, 236, 118, 112, [(256, 'udf-t', 'FW'), (274, 'udf-s', 'PAS[0]=%s' % u['first']),
                                      (292, 'udf-s', 'N = 0x%x' % u['pages']), (314, 'udf-good', 'every page mapped'),
                                      (332, 'udf-s', 'INIT_HCA %s' % u['init'])]))
    p.append('</g></svg>')
    return '<div class="udfig-wrap">%s</div>' % ''.join(p)


def udriver_explainer(u):
    rows = [
        ('Calls', '<code>udriver_dma_map(ctx, mem, int memlen, &amp;dma)</code>',
         '<code>udriver_dma_map_v2(ctx, mem, uint64_t memlen, single_chunk_mapping, &amp;dma)</code>. '
         '<code>udriver_dma_map()</code> stays and now calls it with <code>single_chunk_mapping = 0</code>: same behavior as before.'),
        ('How the buffer reaches the kernel', 'Cut into chunks of 1024 pages (<code>DMA_MAX_PAGES_PER_CHUNK</code>); only the last '
         'one is shorter. One DMA-map request per chunk: %s pages = %s, so %d requests.' % (
             f'{u["pages"]:,}', split(u, ' × 1024 + '), u['chunks']),
         'With <code>single_chunk_mapping = 1</code> the whole buffer is one request: '
         '<code>pages_per_chunk = single_chunk_mapping ? npages : min(1024, npages)</code>. With 0, the old chunking.'),
        ('Device addresses (IOVA)', 'Each request is mapped on its own. Nothing guarantees that the windows touch.',
         'One scatter list for the whole buffer; with the IOMMU on (%s) that is one contiguous IOVA window.' % (
             '012 boots with <code>intel_iommu=on</code>' if u['box'] == 'l-fwreg-012' else
             'the box must boot with <code>intel_iommu=on</code>')),
        ('Buffer size', '<code>int memlen</code>: at most 2 GiB.', '<code>uint64_t memlen</code>; the page count must still fit an '
         '<code>int</code> (checked against <code>INT_MAX</code>). The pool here is 2–5 GiB.'),
        ('Kernel reply (one module for both calls)', 'Already merged adjacent segments and warned when they were not contiguous, '
         'but sized the reply per page (<code>npages</code>), walked <code>npages</code> entries and summed lengths in 32 bit.',
         '<a href="%s1428108">1428108</a>: sizes the reply per merged segment, walks only the mapped entries (<code>nmapped</code>), '
         'sums in 64 bit, logs the contiguous case too, and unmaps on error. <a href="%s1452727">1452727</a>: the segment length is '
         'sent as 64 bit.' % (GERRIT_UDRIVER, GERRIT_UDRIVER)),
    ]
    trs = ''.join('<tr><th scope="row">%s</th><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return (
        '<div class="explainer"><div class="ex-head"><span class="lab">udriver, before and after</span>'
        '<span class="ex-sub"><a href="%s1428108">1428108</a> (merged 08-25) and <a href="%s1452727">1452727</a>, released in '
        'udriver 3.09 (<code>717c5fb</code>)</span></div>%s'
        '<div class="tablewrap"><table class="vs"><thead><tr><th></th><th>Before 3.09: udriver_dma_map</th>'
        '<th>udriver 3.09: udriver_dma_map_v2</th></tr></thead><tbody>%s</tbody></table></div>'
        '<ul class="ex-points">'
        '<li><b>Why the PSF needs it.</b> A RANGE carries one address and a page count; FW uses [first page, first page + N pages) '
        'as one block and computes every page address from the first. With v1, only the first 1024 pages are sure to sit at '
        'the addresses FW computes.</li>'
        '<li><b>What broke on the old call (#22).</b> utopx once mapped the first range with <code>udriver_dma_map</code>, '
        'because it set the global flag only after allocating the pages (#21); v2 already existed. FW rejected the PSF\'s '
        'INIT_HCA with <code>0x9BAE1A</code> and the IOMMU blocked a write to <code>f9fff000</code>, the last page of the range. '
        'The old call still chunks in 3.09, so the split is by call, not by version.</li>'
        '<li><b>Where the contiguity comes from.</b> <code>single_chunk_mapping</code> only makes it one request; the one IOVA '
        'window is the IOMMU\'s doing. Without an IOMMU the addresses are physical and usually scattered, so utopx asserts '
        '<code>PROVIDE_PAGES_RANGE pages are not contiguous</code> before sending.</li>'
        '<li><b>Getting it into builds (#9).</b> utopx pins udriver 3.09 in <code>build.sh</code> '
        '(<a href="%s1526478">1526478</a>); the CI U24 builder was updated by <a href="%s1532124">1532124</a>.</li>'
        '<li><b>One cost (#13).</b> Pinning 2–5 GiB in one call holds udriver\'s lock for a long time; on l-fwreg-217 '
        '(6.x kernel) that hung the host. 012 (5.4 kernel) does not show it.</li>'
        '</ul></div>') % (GERRIT_UDRIVER, GERRIT_UDRIVER, udriver_figure(u), trs, GERRIT_UTOPX, GERRIT_AUTOMATION)


def parts(L, f, u, ri):
    """The PSF's part of the stage (the engine draws the frame, the function rows, the tokens and the banner): the global
    mode lamp, the pool and the PF ICM fed from it under the tokens; the udriver and run scenes over them."""
    pfs = ' and '.join(fn for fn in ('PF0', 'PF1') if f['pf_ops'][fn]) or 'the PFs'
    ev = ('all event_type 0x0a: completions' if set(f['eq_types']) == {'0x0a'} else
          'event types: ' + ', '.join('%s ×%d' % kv for kv in sorted(f['eq_types'].items())) if f['eq_types'] else
          'the log prints no event')
    dev = ri.get('device_name') or 'device'
    p = []
    # device: global mode lamp and the pool
    p.append('<g id="glob" class="glob off"><circle class="lamp" cx="676" cy="56" r="7"/>'
             '<text class="gl-k" x="690" y="52">ICM global mode</text><text class="gl-v" id="glob-v" x="690" y="67">not set</text></g>')
    p.append('<text class="pool-k" x="668" y="104">PSF pool</text><text class="pool-v" id="pool-v" x="980" y="104" text-anchor="end">empty</text>'
             '<rect class="pool-frame" x="668" y="112" width="312" height="30" rx="6"/>'
             '<g id="poolsegs"></g>'
             '<rect id="pool-gone" class="pool-gone" x="668" y="112" width="312" height="30" rx="6"/>'
             '<text id="pool-note" class="pool-note" x="668" y="160">Each range: one contiguous IOVA block, one MANAGE_PAGES</text>'
             '<text id="pool-note2" class="pool-note fn" x="668" y="174"></text>')
    # PF ICM from the pool is the design (FW slides); it stays inside the device. The log only shows 0 pages from software.
    p.append('<g id="feed" class="feed"><path class="feedpath" d="M745 143 L745 170"/><path class="feedpath" d="M895 143 L895 170"/>'
             '<rect class="icmbox pf0" x="690" y="170" width="110" height="22" rx="6"/>'
             '<text class="icm-t" x="745" y="185" text-anchor="middle">PF0 ICM</text>'
             '<rect class="icmbox pf1" x="840" y="170" width="110" height="22" rx="6"/>'
             '<text class="icm-t" x="895" y="185" text-anchor="middle">PF1 ICM</text>'
             '<text class="feed-t" x="668" y="212">By design; the log shows only 0 pages from software</text></g>')
    device = ''.join(p)
    p = []
    # udriver scene
    p.append('<g id="udscene" class="udscene">'
             '<rect class="ud-bg" x="300" y="22" width="694" height="204" rx="10"/>'
             '<text class="ud-k" x="318" y="44">%.0f MiB host buffer · %s pages</text>'
             '<g id="ud-pages"></g>'
             '<text class="ud-lane v1" x="318" y="116">udriver_dma_map · old call, not used in this run (illustration)</text>'
             '<text class="ud-sub" x="318" y="130">%s → %d separate mappings; nothing guarantees they touch</text>'
             '<g id="ud-v1"></g>'
             '<text class="ud-lane v2" x="318" y="186">udriver_dma_map_v2(single_chunk_mapping = 1) · used in this run · one request → one IOVA window (IOMMU on)</text>'
             '<rect class="ud-axis" x="318" y="196" width="660" height="18" rx="4"/>'
             '<rect id="ud-v2bar" class="ud-v2" x="318" y="196" width="660" height="18" rx="4"/>'
             '<text class="ud-addr" x="322" y="226">%s</text><text class="ud-addr" x="974" y="226" text-anchor="end">%s + 4K</text>'
             '</g>' % (u['mib'], f'{u["pages"]:,}', split(u, ' × 1024 pages + 1 × '), u['chunks'], u['first'], u['last']))
    # run scene: counters
    p.append('<g id="runscene" class="runscene"><rect class="ud-bg" x="300" y="22" width="694" height="204" rx="10"/>'
             '<text class="rs-k" x="330" y="66">PF commands, whole run</text><text class="rs-v" id="rs-cmd" x="330" y="104">0</text>'
             '<text class="rs-k" x="560" y="66">events, whole run</text><text class="rs-v" id="rs-ev" x="560" y="104">0</text>'
             '<text class="rs-k" x="760" y="66">page requests</text><text class="rs-v zero" id="rs-pr" x="760" y="104">0</text>'
             '<text class="rs-s" x="330" y="128">%s (config cap: %s × %s ops)</text>'
             '<text class="rs-s" x="560" y="128">%s</text>'
             '<text class="rs-s" x="760" y="128">0x0b would be a page request</text>'
             '<g id="rs-iters"></g><text class="rs-s" x="330" y="214" id="rs-it">iteration 0 / %s</text></g>' % (
                 pfs, ri.get('iters') or '?', ri.get('ops') or '?', ev, f['polls']))
    return dict(title='Host functions, the PCIe and IOMMU path, and the %s with the PSF pool' % dev,
                host='HOST · utopx + udriver', link='PCIe · IOMMU', device_label='DEVICE · %s FW' % dev, device=device,
                overlays=''.join(p))
