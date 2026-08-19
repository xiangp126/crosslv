---
name: creating-nvidia-github-repo
description: Create a new private repository under the NVIDIA GitHub organization (github.com/NVIDIA). Handles OSRB bug filing via nvbugs-cli, module assignment via direct API, and the GitHub Onboarding form. Use when user wants to create a repo under github.com/NVIDIA, mentions NVIDIA GitHub org, OSRB, or open source review board.
metadata:
  author: "Aaron Erickson <aerickson@nvidia.com>"
  tags:
    - github
    - nvidia
    - repository
    - osrb
    - open-source
  languages:
    - bash
    - python
  domain: devops
---

# Create a Private Repo Under github.com/NVIDIA

## Prerequisites

- `nvbugs-cli` authenticated (`nvbugs-cli auth status`)
- `gh` authenticated with NVIDIA org SSO (`gh auth status`)
- `helios-cli` for manager lookup
- **WSL note:** In WSL with Windows-installed binaries, append `.exe` to CLI names (`<tool>-cli.exe`).

## Quick Start

1. Look up manager: `helios-cli user get <username> --toon`
2. File OSRB bug via `nvbugs-cli bug create` (see workflow)
3. Fix the module via direct API (nvbugs-cli bug #470 — `--module` silently fails)
4. User submits form at **https://github-onboarding.nvidia.com/new-repo** with the bug ID
5. Push code and add team

## Key Details

- The env var that enables write operations must be set when filing the bug
- The `--action-id 34 --disposition-id 41` flags are required on bug create
- The `ModuleInfo` field (not `ModuleId`) must be set via direct NVBugs API after creation
- The form cannot be submitted programmatically — user must fill it in browser

## Automation Notes

When executing this skill, do ALL steps automatically:
1. Look up manager via `helios-cli user get <username> --toon`
2. File the OSRB bug via nvbugs-cli with valid auth
3. Fix the module via the curl API workaround — DO NOT SKIP THIS
4. Verify the module stuck
5. Tell the user to submit the form at **https://github-onboarding.nvidia.com/new-repo**
6. After the user confirms the repo exists, push code and add team

The user's GitHub username is `ericksoa`, email is `aerickson@nvidia.com`.
The user's team is `ai-clis`.

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

## Workflows

- [Create NVIDIA GitHub Repo](workflows/create-repo.md) — full step-by-step with OSRB template and API workaround
