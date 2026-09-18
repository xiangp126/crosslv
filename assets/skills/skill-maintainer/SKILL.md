---
name: skill-maintainer
description: >-
  Add, update, validate, or repair skills shared by Claude Code and Codex. Use whenever the user
  asks either agent to create a skill, modify an existing skill, synchronize skills, fix skill
  discovery, or explain where shared skills live.
---

# Maintain shared Claude Code and Codex skills

Claude Code and Codex use the **same physical skill files**. There are no Claude and Codex copies
to merge:

```text
~/myGit/crosslv/assets/skills/          canonical source, tracked by git
~/.claude/skills                       one link to the canonical tree
~/.agents/skills/<name>                one link per shared skill; unrelated Codex skills remain
```

Always edit the canonical path. An installation path may resolve there today, but writing the
source path makes intent clear and avoids recreating two divergent trees.

## Before changing anything

1. Run `jskill check` and `git -C ~/myGit/crosslv status --short`.
2. Resolve the source with `jskill path <name>` and read the complete `SKILL.md` plus only the
   referenced resources needed for this change.
3. Inspect the current diff. Preserve concurrent or uncommitted user changes; never replace a
   whole file merely to apply a small update.

## Modify an existing skill

1. Put behavior true for both agents in `SKILL.md`, `references/`, `scripts/`, or `assets/`.
2. If only tool syntax or runtime behavior differs, keep the shared workflow in `SKILL.md` and
   put the exception in `references/hosts/claude.md` or `references/hosts/codex.md`. Tell the
   shared file when that adapter must be read. Never fork the entire skill for a small host
   difference.
3. Keep credentials, tokens, and machine secrets out of skills. Document credential locations,
   not values.
4. **A skill must not depend on a file outside the skills tree.** Inline the knowledge instead.
   - Allowed: shared infrastructure tools and data sources (`/mswg/...`, `/auto/sw/...`,
     `/.autodirect/...`), anything inside `~/myGit/crosslv` (same version-controlled unit), and
     path *conventions* saying where work goes (`/auto/fwgwork1/$USER/<repo>`,
     `.../bugZilla/<ticket>/`) — those describe a destination, not a dependency.
   - Not allowed: pointing at a document or script under someone's personal work directory. It
     will be deleted or renamed, and the skill is left with a dead link.
   - If such a file holds knowledge the skill needs, **inline it**. If it holds environment state
     that expires (FW versions, which box is usable), the skill should not carry it at all — say
     what to check and how, not what the value currently is.
5. Run `jskill sync`, then `jskill check`. Also run the skill's own tests or scripts when changed.

## Add a skill

Start with:

```bash
jskill add <lowercase-hyphen-name> \
  --description "What the skill does and the concrete situations that should trigger it"
```

Add `--host-adapters` only when Claude Code and Codex genuinely need different invocation
instructions. Replace the scaffold with concise, imperative workflow text. Keep `SKILL.md`
focused; move detailed tables and background into `references/`, deterministic automation into
`scripts/`, and reusable output material into `assets/`.

Finish with:

```bash
jskill sync
jskill check
```

New files become visible immediately through the links, but an already-running agent may cache
its skill inventory or metadata. Start a new session (or restart the current client) when testing
discovery of a newly added skill or changed description.

## Conflict policy

`jskill sync` never overwrites an unrelated real directory or an unknown link. Review the path
first; only then use `jskill sync --backup-conflicts`, which moves it into a timestamped backup.
Git remains the authority for content conflicts: inspect diffs, merge intentionally, and do not
use timestamps or bidirectional `rsync` to choose a winner.
