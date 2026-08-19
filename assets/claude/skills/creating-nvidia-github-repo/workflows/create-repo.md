# Create NVIDIA GitHub Repo — Full Workflow

## Step 1: Look Up Manager

```bash
helios-cli user get <username> --toon
```

Extract `managerChain[0]` name for the OSRB bug.

## Step 2: File OSRB Bug

```bash
nvbugs-cli bug create \
  --synopsis "OSRB: Request to distribute <PROJECT> under <LICENSE>" \
  --bug-type "Software" --div-id 1 \
  --module "Open-Source-Review-Board" \
  --action "Dev - Open - To fix" --action-id 34 \
  --disposition "Open issue" --disposition-id 41 \
  --priority "Unprioritized" --severity "3-Functionality" \
  --description "<SEE TEMPLATE BELOW>" --toon
```

### OSRB Description Template (all 16 fields required)

```
OPEN SOURCE REVIEW BOARD: OSS REQUEST
1. Employee/Manager: <Name> (<user>) / <Manager> (<mgr_user>)
2. Project: <name> — <description>
3. Request Type: c. DISTRIBUTION UNDER NEW OSS LICENSE: Y
4. Summary: <what the code does, no CUDA, license, size>
5. Link: N/A (new project)
6. Interaction: None — standard dependencies only
7. Target: Internal private repo now; public TBD
8. Patents: No
9. CLA: N/A
10. Gov Funded: No
11. Encryption: <Yes/No — describe if yes>
12. Codecs: No
13. License: <e.g., Apache 2.0>
14. Dependencies: <list with licenses>
15. Distribute: Source code
16. Related Bugs: N/A
```

## Step 3: Fix Module (CRITICAL)

The `--module` flag silently fails (issue #470). Must set via API:

```bash
BUG_ID=<from step 2>
TOKEN=$(cat ~/.ai-pim-utils/nvbugs/token)

curl -s "https://nvbugsapi.nvidia.com/nvbugswebserviceapi/api/Bug/GetBug/$BUG_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import json, sys
bug = json.load(sys.stdin)['ReturnValue']
bug['ModuleInfo'] = {'Key': 15766, 'Value': 'Open-Source-Review-Board'}
json.dump(bug, sys.stdout)
" | curl -s -X POST "https://nvbugsapi.nvidia.com/nvbugswebserviceapi/api/Bug/SaveBug" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d @-
```

Verify: response should show `"IsSuccess":true`.

## Step 4: Submit Form

**URL: https://github-onboarding.nvidia.com/new-repo**

Fill in: org (NVIDIA), repo name, description, admin username, email, OSRB bug ID.

## Step 5: Push Code

```bash
git remote add nvidia https://github.com/NVIDIA/<repo>.git
git push nvidia main --force
gh api orgs/NVIDIA/teams/ai-clis/repos/NVIDIA/<repo> -X PUT -f permission=admin
```
