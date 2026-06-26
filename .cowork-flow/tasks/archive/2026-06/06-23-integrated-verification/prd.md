# Phase 9 Integrated Verification

## Goal

Run the integrated acceptance gate after all implementation phases complete.

## Files

- All files changed by child tasks.
- `.cowork-flow/plans/2026-06-23-lifecycle-tdd-quality-gates.md`

## Acceptance Criteria

- All focused tests for gate kernel, TDD skill, lifecycle enforcement, shallow-test rejection, coding standards, agent policy, and workflow/skill sync pass.
- `doctor --subagent-safety` passes on corrected config.
- `git diff --check` passes.
- `npm run test:all` passes.
- Final review confirms root/template copies are synchronized.

## Verification

Run:

```bash
rtk python -m pytest tests/test_quality_gate.py tests/test_test_quality.py tests/test_coding_standards.py tests/test_flow_script_paths.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py -q
rtk .\.cowork-flow\run.cmd doctor --subagent-safety
rtk git diff --check
rtk npm run test:all
```
