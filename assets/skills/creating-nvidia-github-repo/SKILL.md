---
name: creating-nvidia-github-repo
description: Create a new private repository under the NVIDIA GitHub organization (github.com/NVIDIA). Handles OSRB bug filing via nvbugs-cli, module assignment via direct API, and the GitHub Onboarding form. Use when user wants to create a repo under github.com/NVIDIA, mentions NVIDIA GitHub org, OSRB, or open source review board.
---
<!--
Upstream metadata (ai-pim-utils .skills), kept out of the frontmatter, which
jskill limits to name and description:
  author: Aaron Erickson <aerickson@nvidia.com>
  tags: github, nvidia, repository, osrb, open-source
  languages: bash, python
  domain: devops
-->

# Create a Private Repo Under github.com/NVIDIA

## Prerequisites

- `nvbugs-cli` authenticated (`nvbugs-cli auth status`)
- `gh` authenticated with NVIDIA org SSO (`gh auth status`)
- `helios-cli` for manager lookup
- **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Procedure

Run the lookups and checks yourself. Every outward action needs Peter's confirmation first: filing
the OSRB bug (show him the synopsis and the 16-field description), the module fix, and any push.
Commands, the OSRB description template and the API workaround:
[workflows/create-repo.md](workflows/create-repo.md).

1. Look up the manager: `helios-cli user get <username> --toon`
2. File the OSRB bug via `nvbugs-cli bug create` with valid auth; `--action-id 34
   --disposition-id 41` are required on bug create. Writes go through the CLI's own confirmation
   (`AI_PIM_UTILS_PRESENCE` backend) — never set it to skip confirmation unless Peter explicitly
   asks for unconfirmed writes.
3. Set the module. `--module` alone silently fails (nvbugs-cli bug #470): pass
   `--module "Open-Source-Review-Board" --module-id 15766` on create, then check `ModuleInfo` on the
   created bug. If it is still wrong, set `ModuleInfo` (not `ModuleId`) with the direct NVBugs API
   workaround in the workflow — do not skip this.
4. Verify the module stuck.
5. Tell the user to submit the form at **https://github-onboarding.nvidia.com/new-repo** with the
   bug ID. The form cannot be submitted programmatically — the user must fill it in the browser.
6. After Peter confirms the repo exists and approves the push, push the code and add the team.

Identity: ask Peter for the GitHub username, email and the GitHub team that gets admin (or read
them from `gh api user --jq .login` and `git config user.email` and confirm). Never reuse an
identity from an example.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `'NoneType' object has no attribute 'get'` | ModuleInfo not set | Run module fix in workflow |
| `Selected Bug Action and Disposition pair is not valid` | Missing action/disposition flags | Add `--action-id 34 --disposition-id 41` |
| `CreateRepository` permission denied | Can't create via API | Use the onboarding form |
| `bug update --module` panics | CLI bug #470 | Use direct API workaround |
| `Extra data` JSON parse | Telemetry in output | Use `--toon` not `--json` |
| Pre-commit SAML SSO error | Need read:org scope | `gh auth refresh --hostname github.com -s read:org` |

## Approval Requirements

| Action | Approval |
|--------|----------|
| Internal private repo | OSRB bug opened (not necessarily approved) |
| Public repo, permissive license | OSRB + VP approval |
| Contributing CUDA IP | OSRB + E-staff |
| Linking NVIDIA libs to GPL | OSRB + E-staff |

Source: https://nvidia.atlassian.net/wiki/spaces/LEG/pages/2417590658
