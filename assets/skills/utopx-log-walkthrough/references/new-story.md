# A story for another feature

A story is a package under `scripts/stories/<name>/` that decides which steps a page has, what
each step says, what the device side of the stage draws, which design statements the page checks,
and which source lines it cites. The engine (`scripts/wt/`) parses the log, renders the step cards,
folds, run map, statements table, failure step, the stage frame and its script, and resolves the
source lines. A new story writes only its own files; `stories/psf` is the worked example. Add the
name to `NAMES` in `scripts/stories/__init__.py`.

## 1. Engine services

- `wt.log.Log(path)`: `lines` (1-based, ANSI stripped), `rec[n]` = (source, thread, time, level,
  tag, message) for record lines, `tabs[n]` seconds that keep counting across midnight, `ops`
  (one dict per `LOG_OP`: `n`, `time`, `t`, `opcode` with sub-op such as `MODIFY_QP RST2INIT_QP`,
  `fn`, `vhca`, `gvmi`, `dbdf`, `rest`), `fn_info` (function name to VHCA, GVMI, PCI address;
  names are `PSF` or `PF<function number>`), `get_op(opcode, fn, nth, rest, after)` and `first(rx,
  after)` returning None when absent, `op_lines(o)` (the command's lines on its threads),
  `keep(k, fields, keep)` (the lines a step shows), `is_checker(text)` (utopx's second model of a
  function, left out of pages), `verdict()`, `is_debug()`, `info` (the run facts,
  `references/run-info.md`).
- `wt.model.Step(sid, flow, title, lines, marks, notes, slide=[], raw_cap=140)`: marks are
  `(regex on the squeezed line, note number[, set of line numbers])`; notes map numbers to
  HTML; `caption`, `choreo`, `attachments`, `context` lines are set later. `wt.model.Skip(why)`
  leaves a step out.
- `wt.render`: `op_fields(L, o, names)`, `transitions_of(L)`, `stage_at`.
- `wt.failure.failure_step` is added by the engine to every failed run; a story does not build it.
- `wt.coderefs.CodeRef(repo, path, anchor, end=None, within=None, nth=None)`: a source line named
  by its code. `end` is a regex for the last line or a line count; `within` a regex for the
  enclosing C function; `nth` picks one of several matches.

## 2. What the story module exports

| Name | Kind | Used for |
|---|---|---|
| `NAME`, `TITLE` | str | story name, page title |
| `LANES` | tuple of function names | stage rows and run map lanes, in order (up to 6) |
| `FLOWS` | {n: dict(name, color, slide=[...], bottom)} | flow sections and their slide text |
| `FLOW_SHORT` | {n: str} | flow labels in the transport bar |
| `VERDICT` | {key: (label, css class)} | statements table verdicts |
| `SUMMARY_SUB` | str | text under "The run at a glance" |
| `CSS_FILES`, `JS_FILES`, `DIR` | files in the story directory | the story's style and stage hooks, added after the engine's `page.css` and before its `stage.js` |
| `CODEREFS` | {name: CodeRef} | the source lines the text cites as `[[ref:name]]`; `[[tree:<repo>]]` is the run's commit |
| `match(L)` | None or why not | whether the story fits the log |
| `build_steps(L)` | (steps, facts) | the steps in log order; facts must hold `t0`, `t_end` (on the `tabs` clock), `nlines`, `verdict`, `skipped`, `built` |
| `hero(L, f)` | HTML | the page header, with the Result line |
| `scene_parts(L, f)` | dict | `title`, `host`, `link`, `device_label` (the zone labels), `device` (SVG under the tokens), `overlays` (SVG over them) |
| `bands(L, f)` | [(start, end)] per flow | flow bands on the run map |
| `callout(metas)` | HTML or '' | a box under the run map |
| `statement_rows(f)` | [(flow, text, verdict key, what the log shows, step id)] | statements table |
| `fill(L, f)` | dict | values formatted into statements and flow texts |
| `flow_intro(fl, f)` | str | "In this log" text of a flow |
| `flow_extra(fl, L, steps, trans, f, fill)` | HTML or '' | a block under a flow head |
| `footer(L, f)` | HTML | the footer |
| `page_data(L, f, mapx)` | dict | extra keys for the story's script (`D.<key>`) |

## 3. The stage

The engine draws the frame (`wt/scene.py`): the host zone with one row per lane (name, PCI
address and GVMI, the HCA stage chip, the rail), the device zone, the token layer and the pass
or fail banner. Its script (`wt/stage.js`) runs playback, the transport and keyboard, the
caption, the chips, the command tokens (`cmds`: function, request label, reply label, reply kind
`ok`, `zero`, `info`, `blocked` or `bad`, and the command's LOG_OP line; `par` sends them
together), the banner (`passed`, `banner: 'fail'`), the run map playhead and the scroll sync.

The chips follow the commands: the page data holds, per step, each function's HCA stage before
the first command and after each one (`chips`), computed from the stage changes each command's own
threads print, before or after its LOG_OP line. A command without a line (one utopx did not send)
leaves the chips as they are. With reduced motion the chips show the step's end at once.

The story's script defines `window.WALK_STORY = {init, chipTags, apply}`, all optional:

- `init(api)` once: build what the device side needs (`api.D` page data, `api.$` by id,
  `api.el` SVG element, `api.reduce` reduced motion, `api.perCmd(cmds)` the time per command).
- `chipTags(choreo, stages)` per step: {function: word} added to that function's chip.
- `apply(index, choreo, prev, api)` per step, after the chips and before the tokens: update the
  device side from the story's own choreography keys. Hand every animation to `api.track()`;
  the next step cancels it.

## 4. Writing builders

- One builder per step, in log order, decorated with `@add` inside `build()`; it returns a
  `Step` or raises `Skip`. Look commands up with `get_op` and raise `Skip` with a readable reason
  when one is missing; never index into a list that may be short.
- Compute every number from the log; keep feature history in the text only with its link.
- Captions and choreography are computed per step in one place (`stage()` in the PSF story).
- Cite source lines with `[[ref:name]]`, never a typed `file:line`: `check` rejects one.
- After each change: the unit tests, then build every published page of the feature, `golden`
  against its published copy, `check --log` each.
