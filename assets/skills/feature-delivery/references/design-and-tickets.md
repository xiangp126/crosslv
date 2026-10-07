# Documents and tickets a feature carries

Read in Phase 0–1, when establishing what exists (or should exist) before code.

## The document set

The names overlap, and a feature commonly also has an **older superseded set** from a previous
attempt — always establish which set is current.

| Document | Lives in | Audience | Settles |
|---|---|---|---|
| **Feature Request** | SharePoint `NBU-Architecture/SWArch`, `Feature Request #<id> <title>.docx` | everyone | the **numbered requirements** (`Req 1..N`) — the acceptance contract for Phase 6 |
| **HLD** | Confluence, Networking FW | FW + Ver | how it works; reviewed before coding starts |
| **MAS** | Confluence | FW | FW-side architecture spec |
| **FWV uArch** | Confluence | **Ver** | what the **test tool** must implement and check — the contract between architecture and test tool; it **blocks review** (SKILL.md Phase 1) |
| **design plan / MTBC** | Confluence | management | scope and schedule |
| meeting recaps | Teams | everyone | decisions that exist nowhere else |

Reading and publishing Confluence: skill `managing-confluence` (the MCP is read-only; publish
through the raw-curl helper).

**Superseded sets are a trap**: the old and the current set are both reachable from search; only
one is in force. The first time you resolve which is which, record it in the ledger with links.
PSF example: the "previous docs" (a `[MAS][Presi][CX10] New page supplier` pair) vs the current
set for `ICM Page supplier: support global pool delegation`.

## Tickets

| Ticket | Tracker | Why it exists |
|---|---|---|
| FW feature | Redmine | the implementation work |
| **`[Ver]` feature** | Redmine, separate id | the verification work — **a separate ticket, not a sub-task** |

gerrit enforces this: the `Redmine-Issue` label is a submit requirement, and a change without a
valid one stays `NOT_READY` even with `Code-Review+2`. (PSF: FW `#4838398`, Ver `#4965917`.)

Opening tickets: the default channel is Redmine — skill `utopx-regression-ticket` carries the
field conventions, including that a firmware *defect* found along the way goes to the Design
project instead. Only an explicit "open a CI ticket" means the ServiceNow form (skill
`ci-support-ticket`).

## Owners

A feature has an owner per repo, usually different people. Before reporting status, know:

- the **FW owner** (`golan_fw`) and the **test-tool owner** (`fw_ver/utopx`);
- which of them is blocked on the other;
- who the *actual* reviewers are on each side — see `review-and-merge.md`.

When taking over, confirm that the change you were told to base on ("apply this commit first")
belongs to the person handing over, and establish its relationship to the stack — it may belong to
someone else entirely.
