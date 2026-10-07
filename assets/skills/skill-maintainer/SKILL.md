---
name: skill-maintainer
description: >-
  Add, update, validate, or repair skills shared by Claude Code and Codex. Use whenever the user
  asks either agent to create a skill, modify an existing skill, synchronize skills, fix skill
  discovery, or explain where shared skills live.
---

# Maintain shared Claude Code and Codex skills

Claude Code and Codex load the **same physical skill files**; there are no per-client copies to
merge:

```text
~/myGit/crosslv/assets/skills/          canonical source, tracked by git
~/.claude/skills/<name>                one link per shared skill; Claude Code's own synced/ stays here
~/.agents/skills/<name>                one link per shared skill; unrelated Codex skills remain
```

- Both clients always get the same set of links: a skill is shared with both or with neither.
- Each client's skills directory is a real directory, never a link to the canonical tree: the
  client writes into it (Claude Code keeps its synced account skills in `synced/`), and through a
  tree link those writes landed in the repository.
- Always edit the canonical path, even when an installation path resolves there today — it keeps
  intent clear and avoids recreating two divergent trees.

## Before changing anything

1. Run `jskill check` and `git -C ~/myGit/crosslv status --short`.
2. Resolve the source with `jskill path <name>`; read the complete `SKILL.md` plus only the
   referenced resources this change needs.
3. Inspect the current diff. Preserve concurrent or uncommitted user changes; never replace a
   whole file to apply a small update.

## Modify an existing skill

1. Behavior true for both agents goes in `SKILL.md`, `references/`, `scripts/` or `assets/`.
2. When only tool syntax or runtime behavior differs, keep the shared workflow in `SKILL.md` and
   put the exception in `references/hosts/claude.md` or `references/hosts/codex.md`; say in the
   shared file when that adapter must be read. Never fork a whole skill for a small host
   difference.
3. No credentials, tokens or machine secrets in skills — document credential locations, not
   values.
4. **A skill must not depend on a file outside the skills tree** — inline the knowledge instead.
   - Allowed: shared infrastructure tools and data sources (`/mswg/...`, `/auto/sw/...`,
     `/.autodirect/...`); anything inside `~/myGit/crosslv` (same version-controlled unit); path
     *conventions* saying where work goes (`/auto/fwgwork1/$USER/<repo>`,
     `.../bugZilla/<ticket>/`) — a destination, not a dependency.
   - Not allowed: a document or script under someone's personal work directory — it gets deleted
     or renamed and leaves a dead link. Inline the knowledge it holds; if it holds environment
     state that expires (FW versions, which box is usable), carry none of it — say what to check
     and how, not the current value.
5. Write for an agent, in English only: no CJK characters in any skill file, including templates,
   samples and script comments or messages. A script that must still match legacy non-English text
   writes those markers as `\uXXXX` escapes. State the procedure and the rules — commands, paths,
   verbatim error signatures, numbers, decision criteria — and leave out incident stories, dates of
   discovery, who decided what, and repeated warnings. Keep a reason only when it changes how the
   rule is applied, as one clause. Check with:
   `grep -rlP '[\x{4e00}-\x{9fff}]' ~/myGit/crosslv/assets/skills` (must print nothing).
6. Run `jskill sync`, then `jskill check`; also run the skill's own tests or scripts when they
   changed.

## Add a skill

```bash
jskill add <lowercase-hyphen-name> \
  --description "What the skill does and the concrete situations that should trigger it"
```

- Add `--host-adapters` only when Claude Code and Codex genuinely need different invocation
  instructions.
- Replace the scaffold with concise, imperative workflow text. Keep `SKILL.md` focused: detailed
  tables and background go to `references/`, deterministic automation to `scripts/`, reusable
  output material to `assets/`.
- Finish with:

```bash
jskill sync
jskill check
```

New files are visible immediately through the links, but a running agent may cache its skill
inventory or metadata: start a new session (or restart the client) to test discovery of a new
skill or a changed description.

## Conflict policy

- `jskill sync` never overwrites an unrelated real directory or an unknown link. Review the path
  first; only then use `jskill sync --backup-conflicts`, which moves it into a timestamped backup.
- Git is the authority for content conflicts: inspect diffs and merge intentionally; never let
  timestamps or bidirectional `rsync` choose a winner.
