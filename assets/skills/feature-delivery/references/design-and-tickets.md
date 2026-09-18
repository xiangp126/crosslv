# Documents and tickets a feature carries

Read this in Phase 0–1, when establishing what exists (or should exist) before code.

## The document set

Two things make this confusing: the names overlap, and a feature commonly has an **older
superseded set** from a previous attempt. Always ask which is current.

| Document | Lives in | Audience | Settles |
|---|---|---|---|
| **Feature Request** | SharePoint `NBU-Architecture/SWArch`, `Feature Request #<id> <title>.docx` | everyone | the **numbered requirements** (`Req 1..N`) — the acceptance contract for Phase 6 |
| **HLD** | Confluence, Networking FW | FW + Ver | how it works; reviewed before coding starts |
| **MAS** | Confluence | FW | FW-side architecture spec |
| **FWV uArch** | Confluence | **Ver** | what the **test tool** must implement and check |
| **design plan / MTBC** | Confluence | management | scope and schedule |
| meeting recaps | Teams | everyone | decisions that exist nowhere else |

Reading and publishing Confluence: skill `managing-confluence` (the MCP is read-only; publish
through the raw-curl helper).

### The uArch is the one that blocks

It is the contract between the architecture and the test tool. A reviewer who has not seen the
code agree with the uArch can, and does, suspend review of the largest file in the change:

> PSF, on the biggest file of the utopx change: *"will review after aligning with uArch"* + a link
> to the FWV uArch page. That comment sat unresolved for weeks while patchsets kept coming. No
> number of patchsets would have cleared it — only the document.

If the uArch is missing, stale, or contradicts the code, resolving that **is** the work.

### Superseded sets are a trap

PSF had "previous docs" (a `[MAS][Presi][CX10] New page supplier` pair) plus the current set for
`ICM Page supplier: support global pool delegation`. Both are reachable from search; only one is
in force. Record in the ledger which is which, with links, the first time you resolve it.

## Tickets

| Ticket | Tracker | Why it exists |
|---|---|---|
| FW feature | Redmine | the implementation work |
| **`[Ver]` feature** | Redmine, separate id | the verification work — **a separate ticket, not a sub-task** |

gerrit enforces this: the `Redmine-Issue` label is a submit requirement, and a change without a
valid one stays `NOT_READY` even with `Code-Review+2`. PSF had FW `#4838398` and Ver `#4965917`.

Opening tickets: default channel is Redmine (skill `utopx-regression-ticket` carries the field
conventions, including that a firmware *defect* found along the way goes to the Design project
instead). Only an explicit "open a CI ticket" means the ServiceNow form
(skill `ci-support-ticket`).

## Owners

A feature has an owner per repo, and they are usually different people. Before reporting status,
know:

- **FW owner** (`golan_fw`) and **test-tool owner** (`fw_ver/utopx`)
- which of them is blocked on the other
- who the *actual* reviewers are on each side — see `review-and-merge.md`

When taking over, confirm the change you were told to base on belongs to the person handing over.
On PSF the handover said "apply this commit first"; that change belonged to someone else entirely
and its relationship to the stack was never established.
