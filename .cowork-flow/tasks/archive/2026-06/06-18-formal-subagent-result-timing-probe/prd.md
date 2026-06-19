# Probe formal subagent result timing

## Goal

Determine whether recent formal `cowork-*` child runs failed because:

- the child never produced a usable final result, or
- the child was still executing while the main session stopped waiting too early.

## Scope

- Create a minimal formal `cowork-implement` probe under this task.
- Measure runtime creation, binding, child-side marker writes, and result return.
- If needed, run a deliberate slow variant to distinguish "no return channel" from
  "return arrived after a longer wait".
- Summarize the verdict with runtime evidence.

## Non-Goals

- Do not change product behavior or architecture in this task.
- Do not archive or commit this probe unless the user asks.
- Do not infer success from model text alone; use runtime state and filesystem
  evidence.

## Acceptance Criteria

1. A fast formal probe is dispatched through the real `cowork-implement`
   runtime-context path.
2. The probe records whether the child bound successfully.
3. The probe records whether the child executed task work by writing a marker
   file under the task directory.
4. The probe records whether a final usable result returned to the parent.
5. The final conclusion distinguishes between:
   - no execution,
   - execution without result return,
   - or successful return after sufficient wait time.

## Related Files

- `.cowork-flow/spec/core/dispatch.md`
- `.cowork-flow/adapters/codex/adapter.yaml`
- `.cowork-flow/plans/2026-06-18-formal-subagent-result-timing-probe.md`
- `.cowork-flow/tasks/06-18-formal-subagent-result-timing-probe/`

## Verification

- `rtk .\\.cowork-flow\\run.cmd subagent dispatch ...`
- `rtk .\\.cowork-flow\\run.cmd subagent status <runtime_id>`
- marker files written under this task directory
- adapter wait results observed by the parent session
