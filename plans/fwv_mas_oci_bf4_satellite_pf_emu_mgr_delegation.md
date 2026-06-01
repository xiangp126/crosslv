# [FWV][MAS] OCI BF-4 Satellite PF Emulation Manager Capability Delegation

<!-- confluence-page-id: 3530037909 -->
<!-- confluence-space: FW -->
<!-- confluence-url: https://nvidia.atlassian.net/wiki/spaces/FW/pages/3530037909 -->

<!-- Confluence property table: rendered as page-properties on the live page.
     Field names colored rgb(0,90,171) belong to the FWV side (matches reference MAS convention). -->

<table>
<tbody>
<tr><th><p><strong>Marketing (POR) RM ticket:</strong></p></th><td><p><a href="https://redmine.mellanox.com/issues/4690480">https://redmine.mellanox.com/issues/4690480</a> &mdash; [OCI][BF-4] virtio-net needs emulation capabilities to a PF or SF<br/><a href="https://redmine.mellanox.com/issues/4284608">https://redmine.mellanox.com/issues/4284608</a> &mdash; [SNAP NVMe]VBLK[VFS][BF4] support &quot;RDMA exclusive mode&quot; for container</p></td></tr>
<tr><th><p><strong>FW feature owner</strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:40713676-b8af-4b85-bedb-ff0efd65d36c" /></ac:link>&nbsp; <ac:link><ri:user ri:account-id="712020:dea38615-00d2-4aac-916b-2ed25de0bd1d" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong>FWV feature owner (author)</strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:8a13b619-401d-4173-8233-d6516e03e521" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong><span style="color: rgb(0,90,171);">FWV mentor</span></strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:e7c69c44-140c-4357-93ea-e9b7163e00f9" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong><span style="color: rgb(0,90,171);">FWV uArch owner</span></strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:cd3efc1b-1350-407f-a511-1c90fb18bbc7" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong>Arch/PRM owner</strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:c13ab396-b466-44ab-8f3d-209523283fb3" /></ac:link>&nbsp; <ac:link><ri:user ri:account-id="712020:a5ebddf1-1b84-46cd-b519-a12c0e7c2265" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong>FW uArch owner</strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:92339f73-df23-4d55-b82e-1eeeb62f8ef1" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong><span style="color: rgb(0,90,171);">FW design owner</span></strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:40713676-b8af-4b85-bedb-ff0efd65d36c" /></ac:link>&nbsp; <ac:link><ri:user ri:account-id="712020:dea38615-00d2-4aac-916b-2ed25de0bd1d" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong>SW owner</strong></p></th><td><p><ac:link><ri:user ri:account-id="712020:5390b0dd-5590-4b37-8b92-9766bc4be386" /></ac:link>&nbsp; <ac:link><ri:user ri:account-id="712020:cb225456-3c4d-483e-8606-7f5668f6e82c" /></ac:link>&nbsp; <ac:link><ri:user ri:account-id="712020:99765e11-549a-4e3e-9e91-3319c4cd8a2b" /></ac:link>&nbsp;</p></td></tr>
<tr><th><p><strong>Arch doc</strong></p></th><td><p>DPU emulation manager cap delegation architecture (SharePoint: <code>vr_bf4_oci_partition_arch.docx</code>) &mdash; <em>TODO: replace with SharePoint URL</em></p></td></tr>
<tr><th><p><strong>HLD</strong></p></th><td><p><a href="https://nvidia.atlassian.net/wiki/spaces/FW/pages/3395678597">[HLD] OCI BF-4 Satellite PF Emulation Manager Capability Delegation</a></p></td></tr>
<tr><th><p><strong>IAS page</strong></p></th><td><p>N/A</p></td></tr>
<tr><th><p><strong>MTBC</strong></p></th><td><p><a href="https://nvidia.atlassian.net/wiki/spaces/FW/pages/3501921204">MTBC tracking page</a></p></td></tr>
<tr><th><p><strong>Device / FW scope</strong></p></th><td><p>BF-4, branch master</p></td></tr>
<tr><th><p><strong>Date</strong></p></th><td><p>2026-05-28</p></td></tr>
</tbody>
</table>

---

## Feature description

> See HLD for full description. This MAS focuses on the verification side only.

### Arch perspective (high level)
OCI BF-4 partitions DPU services into a **SmartNIC partition** (ECPF/eswitch/resource management) and a **HostNIC partition** (NVMe/virtio emulation). This feature lets the primary emulation manager delegate emulation-manager capabilities to another VHCA so emulation can run from the lower-privilege partition. **Phase 1 (July-26) targets the satellite PF only**; SF and DPU VF are future.

### HW/FW perspective (high level)
DMS sets **exactly one** DMS-visible manager cap (`virtio_net_device_emulation_manager` or `nvme_device_emulation_manager`) on the destination VHCA via `SET_HCA_CAP(other=1)`. FW derives the supporting HCA caps internally, drives a per-emulation-type state machine `DISABLED → INIT → RUNNING`, and enforces a single active manager **per emulation type**. DMS confirms success via `QUERY_HCA_CAP`.

### Verification perspective (high level)
Build on existing Utopx emulation-manager infra. Add:
- A delegated-manager model in the verification environment that mirrors FW's per-GVMI `ctx.type[VNET|NVME].{state, refcnt}` and the scratchpad `active_manager_gvmi[type]`.
- Stimulus to issue `SET_HCA_CAP(other=1)` from the SNIC-partition GVMI to a satellite-PF GVMI and to drive device-emulation / hotplug create/destroy from the delegated manager.
- Checks across `QUERY_HCA_CAP`, `QUERY_EMU_FUNC_INFO`, `QUERY_EMULATED_RESOURCES_INFO`, `QUERY_EMULATED_HOSTS_INFO`, RXT/RXC, ICM addressing, DPA doorbell, and all FLR paths.

---

## Implementation — Generation

### Generation
BF-4 OCI partition profile with at least one satellite PF (DPU PF in FW scope). Generation must support both VNET-only, NVME-only, and dual VNET+NVME delegation on the same satellite PF, plus the two-satellite-PF case (one type each).

### Relevant operations
**Existing** — `SET_HCA_CAP`, `QUERY_HCA_CAP`, `QUERY_EMU_FUNC_INFO`, `QUERY_EMULATED_RESOURCES_INFO`, `QUERY_EMULATED_HOSTS_INFO`, device emulation object create/modify/query/destroy, hotplug device create/destroy, FLR, DPA CQ doorbell setup.
**New** — none.

### Existing mechanisms
Reuse:
- Utopx emulation-manager generation infrastructure (the same one used by existing ECPF default-manager flows).
- Existing satellite-PF / `is_esw_gvmi_dpu_pf()` generation.
- Existing HCA-cap generation framework.
- ObjectChangeEvent infrastructure for delegated resource notifications.

### Generation change
Add a delegated-manager stimulus on satellite-PF GVMIs:
1. Pick a satellite-PF VHCA on which delegation is allowed.
2. Issue `SET_HCA_CAP(other=1, vhca_id=sat_pf)` with **exactly one** of `virtio_net_device_emulation_manager` / `nvme_device_emulation_manager`.
3. `QUERY_HCA_CAP(other=1, vhca_id=sat_pf)` and treat any mismatch as the unsupported/older-FW path (skip remainder for that GVMI).
4. After success, route subsequent device-emulation create/destroy and hotplug create/destroy through the satellite-PF GVMI for the chosen type.
5. Randomly mix in revocation attempts (some at INIT, some at RUNNING — the latter must be rejected) and double-delegation attempts (must be rejected when another GVMI already RUNNING for that type).

---

## Verification

### Relevant checkers
- **HcaCapChecker** — `QUERY_HCA_CAP(other=1)` reports the requested manager cap and FW-derived supporting caps only after `SET_HCA_CAP` was accepted.
- **EmuManagerChecker** (extend) — per-GVMI/per-type state machine, refcount, and `active_manager_gvmi[type]` exclusivity.
- **EmuFuncInfoChecker / EmulatedResourcesInfoChecker / EmulatedHostsInfoChecker** — emulated-function → delegated-manager relation.
- **RxtChecker / RxcChecker** — manager-related routing entries point to delegated GVMI.
- **DpaDoorbellChecker** — DPA CQ doorbell flow uses delegated manager table index.
- **IcmChecker** — emulation resource ICM addressing resolves through the delegated manager GVMI.
- **FlrChecker** — delegated-manager cleanup invoked on all five FLR paths.
- **ObjectChangeEventChecker** — events for delegated resources are routed correctly.

### Existing mechanisms
The existing emulation-manager checker tracks one default manager per emulated GVMI and is invoked from device-emulation create/destroy and hotplug create/destroy paths. It already cross-checks `QUERY_EMU_FUNC_INFO` and `QUERY_EMULATED_RESOURCES_INFO`. We extend it from "single manager" to "manager resolved per emulation type, default or delegated."

### Feature verification

Maintain a verification-side model:

```
model.gvmi[g].type[VNET|NVME] = { state ∈ {DISABLED, INIT, RUNNING}, refcnt }
model.active_manager_gvmi[type] ∈ {INVALID, gvmi}
```

Transitions in the model:
- `SET_HCA_CAP(other=1, dst=g)` with one manager cap:
  - Validate caller privilege, `is_esw_gvmi_dpu_pf(g)`, no unsupported cap fields.
  - If `model.gvmi[g].type[t].state == DISABLED` and enabling: predict accept → state = INIT (and predict HW init).
  - If state == INIT and disabling: predict accept → state = DISABLED (and predict HW cleanup when all other types DISABLED).
  - If state == RUNNING and disabling (revocation): predict **reject**.
- Device-emulation **object create** on emu_gvmi resolved to manager g, type t:
  - If `model.active_manager_gvmi[t] == INVALID` → set to g, model.gvmi[g].type[t].state INIT → RUNNING.
  - Else if `model.active_manager_gvmi[t] != g` → predict **reject**.
  - Else → predict accept and `refcnt++`.
- Device-emulation **object destroy** → `refcnt--`; when 0, clear `active_manager_gvmi[t]` and move state RUNNING → INIT.
- Hotplug device create/destroy → **does not** change state or refcount.

Cross-check the model against:
- `QUERY_HCA_CAP(other=1)` result fields.
- `QUERY_EMU_FUNC_INFO` (emulated-function → manager mapping).
- RXT/RXC and TOC programming (delegated entries).
- DB/MSI-X resource ownership.
- DPA CQ doorbell programming.
- FLR cleanup predictions.

### Uncertainty
- **Cap-set vs driver-active race** — if the satellite-PF driver becomes active between FW's check and the cap-set, FW must reject. Add uncertainty window in generation and assert FW returned reject.
- **Concurrent create from two GVMIs same type** — only one wins; loser is rejected. Add uncertainty over which create wins, but require exactly one accept.
- **Object-change events ordering** during state transitions.

---

## Side effects (how does this feature affect other features)

### Effects
- HCA cap reporting becomes **per-manager** rather than default-manager-only — all consumers of HCA cap state must be re-verified for the delegated manager.
- Emulation resource ICM addressing resolves through the delegated manager GVMI when delegation is active.
- FLR semantics now include delegated-manager cleanup across five FLR paths (manager FLR, ECPF FLR, emulated-function FLR, page-supplier FLR, eswitch-manager FLR).
- DPA CQ doorbell flows must use the delegated manager table index.

### Solutions
- **Generation** — Reduce probability of FLR + cap-set races to keep tests deterministic at first; gate aggressive concurrency under a dedicated stress flavor.
- **Verification** — Audit Utopx checkers/operations that currently call into "default manager" logic (any equivalent of `get_default_gvmi_emulation_manager()`); route through the per-type resolver.
- **Debug** — Extend resource-dump checks: delegated manager state per GVMI, enabled emulation-type bitmap, required-cap bitmap, running resource refcount, and active/running manager → emulated-function mapping.

### FLR
Cover delegated-manager cleanup for each of the five FLR paths from HLD:
1. Manager FLR (the delegated satellite PF itself).
2. ECPF FLR (default manager).
3. Emulated function FLR.
4. Page supplier FLR (note: HLD states page supplier remains ECPF for satellite PF — verify).
5. eswitch manager FLR.

Specific scenarios:
- FLR while delegated state == INIT (no running resources).
- FLR while state == RUNNING with non-zero refcount.
- FLR during a hotplug create/destroy window.
- FLR followed by re-delegation to the same or a different GVMI.

### Security
Negative tests:
- Non-authorized caller (non-ECPF / non-default-manager) attempts `SET_HCA_CAP(other=1)` for a manager cap → reject.
- Destination is not a satellite PF in Phase 1 → reject.
- Satellite PF driver is active during cap setting → reject.
- Cross-VHCA object access from the delegated manager beyond the allowed object types → reject (cross-check against object-type allow-list once specified by arch — TBD per HLD).
- Revocation while RUNNING → reject (ownership-consistency guarantee).

---

## Flavors and limitations

### Good / Normal / Error
- **Good** — Single enable/disable cycle per emulation type on a single satellite PF, no resources running.
- **Normal**
  - VNET + NVME delegated to the same satellite PF (both types active).
  - Two satellite PFs, one type each.
  - Full life-cycle: enable → create device emulation object(s) → hotplug attach/detach → destroy → disable.
- **Error** (must be predicted-reject)
  - Non-satellite destination.
  - Unsupported / multi-cap `SET_HCA_CAP` payload.
  - Revocation while RUNNING.
  - Second GVMI tries to become RUNNING for a type already RUNNING.
  - Satellite-PF driver active during cap-set.
  - Invalid emulated-function ↔ delegated-manager relation on resource create.
  - FW returns failure → state stays/returns to DISABLED.

### Generation holes
- **SF and DPU VF as delegated managers** — explicitly out of scope for Phase 1.
- **Page supplier delegation** — page supplier remains ECPF; not exercised.
- **Performance/data-path stress** — not in scope (control-path feature).

### Main Database/Algorithm changes
Extend the Utopx-side emulation-manager database: add a per-GVMI per-type record `{state, refcnt}` and a global per-type active-manager pointer. Replace any direct "default manager" lookups in checkers with the per-type resolver.

---

## Coverage (critical)

1. **State machine — per emulation type per candidate-manager GVMI**
   - `DISABLED → INIT` via `SET_HCA_CAP`.
   - `INIT → RUNNING` on first device-emulation object create.
   - `RUNNING → INIT` on last device-emulation object destroy.
   - Revoke-while-RUNNING → reject.
   - Revoke-while-INIT → accept, clean HW correctly.
2. **Hotplug-only path** — explicit assertion: hotplug create alone does **not** transition state or change refcount.
3. **Active-manager exclusivity per type** — both same-GVMI-both-types and different-GVMI cases. Reject second RUNNING.
4. **Cap reporting** — `QUERY_HCA_CAP(other=1)` reflects the manager cap and FW-derived supporting caps. Pre-`SET` query must not show the cap.
5. **DB/MSI-X/ICM** — addressing follows delegated manager GVMI.
6. **RXT/RXC + TOC** — manager-related entries programmed against delegated GVMI; emulated-GVMI TOC remains owned by the emulated GVMI (per HLD: emulation TOC ownership does not move).
7. **DPA CQ doorbell** — flow uses delegated manager table index.
8. **FLR cleanup** — all five FLR paths.
9. **Regression** — existing ECPF/default-manager flows untouched when no delegation configured (older-tool compatibility).
10. **Object Change Event** — emitted correctly for delegated resources.
11. **`QUERY_EMU_FUNC_INFO` / `QUERY_EMULATED_RESOURCES_INFO` / `QUERY_EMULATED_HOSTS_INFO`** — return expected manager/function relation.
12. **Negative matrix** — all rejects in §Error above.

### Test environment
- **Utopx** — Primary. Build on Hostless-DPA-style model (per the recent `[FWV][MAS] Hostless PCC algo Live Update` pattern).
- **NICX** — N/A (per MTBC).
- **QA / Performance / E2E** — TBD (per MTBC); confirm scope with mentor at MAS review.

---

## IAS related section
N/A (HLD declares no IAS page). No IAS update required.

---

## Related docs / links

- [HLD] OCI BF-4 Satellite PF Emulation Manager Capability Delegation — https://nvidia.atlassian.net/wiki/spaces/FW/pages/3395678597
- MTBC tracking — https://nvidia.atlassian.net/wiki/spaces/FW/pages/3501921204
- FWV MAS methodology — https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830359041
- MAS template guide — https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830201923
- Reference MAS (recent style) — `[FWV][MAS] Hostless PCC algo Live Update` — https://nvidia.atlassian.net/wiki/spaces/FW/pages/2830148117
- Arch doc (SharePoint) — `vr_bf4_oci_partition_arch.docx`

---

## Milestones (mirror from MTBC)

| Milestone | Date | Notes |
|---|---|---|
| MAS Review Done | 2026-06-05 | reviewers: FWV mentor, FWV uArch owner, FW design owner |
| Resource management coverage | 2026-07-03 | Hotplug/HotUnplug, create/modify/query/destroy emu objects, QUERY_EMU_FUNC_INFO, QUERY_EMULATED_RESOURCES_INFO, QUERY_EMULATED_HOSTS_INFO, Object Change Event |
| All tests pass | 2026-08-01 | Dynamic MSIX, Dynamic vQueue, Live Update |
| FLR emulation manager | 2026-08-07 | open: how to handle hotplug device during FLR |
| Verification effort | 14 WW (planned) | |
