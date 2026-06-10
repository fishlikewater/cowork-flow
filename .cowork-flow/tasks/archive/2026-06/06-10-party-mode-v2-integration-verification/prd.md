# Party Mode V2 Integration Verification PRD

## Goal

Perform integrated verification and hardening after Party Mode V2 runtime, debate rules, and host assets are implemented.

## Scope

This is the final integration task. It adds end-to-end runtime simulation tests, verifies host-neutral behavior across Codex, Claude Code, and OpenCode assets, fixes documentation drift, and runs targeted verification.

## Files

- `tests/test_party_mode_v2.py`
- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`
- `test/opencode-plugin.test.js`
- `README.md`
- `.cowork-flow/plans/2026-06-10-party-mode-v2-runtime-board.md`
- `.cowork-flow/tasks/06-10-party-mode-v2-runtime-board-design/design.md`

## Requirements

- Simulate at least three agents through init, publish, view, respond, advance, and finalize.
- Verify moderator monitor output contains status and next actions, not synthesized opinions.
- Verify shared docs stay host-neutral.
- Verify root/template and host-specific assets are synchronized.
- Fix README drift around current Party Mode V1 defaults if still present.

## Acceptance Criteria

- End-to-end simulation reaches both converged and max-rounds-unconverged outcomes.
- V1 Party Mode remains available and unchanged.
- V2 assets exist for Codex, Claude Code, and OpenCode surfaces.
- Targeted Python and Node tests pass.
- `rtk git diff --check` passes.

## Verification

```powershell
rtk pytest tests/test_party_mode_v2.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py
rtk npm test -- test/opencode-plugin.test.js
rtk git diff --check
```
