# RCCA & Fix Info Workflow

Read Root Cause Corrective Action (RCCA) data and fix information for bugs (root cause, what was
tested, risk assessment) — for example to review fix info before closing a bug — and manage RCCA
escape tracking data.

## 1. Get Fix Information

```bash
# Root cause, fix details, testing info, risk assessment
nvbugs-cli rcca fix-info <bug-id> --json
```

Fix info is a single object per bug, not a list. Key fields: `RootCause`, `FixInfo`, `WhatToTest`,
`RiskAssessment`, `IsFixInfoNeeded`, `IsArbNeeded`, `ArbAssignee`; all fields are returned,
including `WhatToTestAreasAffected`, `TestRunPriorToCheckin`, `PerforceUnitTestInfo`.

## 2. Writing Fix Info

nvbugs-cli has no command that writes fix info: `rcca fix-info` only reads it, and neither
`bug update` nor any `bug specialized` command sets `RootCause` or `FixInfo`. Ask Peter to fill
those fields in the NVBugs web UI.

## 3. RCCA Escape Data

Escape areas and escape types are reference data (division-independent).

```bash
# List coverage escape areas
nvbugs-cli rcca escape-areas --json

# List coverage escape types
nvbugs-cli rcca escape-types --json

# List test escape types
nvbugs-cli rcca test-escape-types --json

# Get test escape data for a specific bug
nvbugs-cli rcca test-escape-data <bug-id> --json

# Save test escape data (JSON from a file, or inline with --data '<json>')
nvbugs-cli rcca save-test-escape --data-file escape-data.json --json
```

## 4. RCCA Division Lookup Mappings

```bash
# Add an RCCA division lookup mapping (all four flags required)
nvbugs-cli rcca mapping add --rcca-division GPU --lookup-type-name EscapeArea \
  --lookup-name Functional --app-div-id 100 --json

# Delete an RCCA division lookup mapping
nvbugs-cli rcca mapping delete --record-id 123 --json
```
