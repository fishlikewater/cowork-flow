# Phase 7 Agent Policy Gate

## Goal

Make `doctor --subagent-safety` and tests share the same fixed-agent and advisory-agent safety rules.

## Files

- `.cowork-flow/scripts/common/agent_policy.py`
- `template/.cowork-flow/scripts/common/agent_policy.py`
- `.cowork-flow/scripts/doctor.py`
- `template/.cowork-flow/scripts/doctor.py`
- `.codex/agents/default.toml`
- `tests/test_cowork_agents.py`

## Acceptance Criteria

- Advisory agents `worker`, `default`, and `explorer` require `multi_agent = false`.
- Advisory agents require `features.multi_agent_v2.enabled = false`.
- Advisory agent instructions explicitly prohibit spawning, waiting for, listing, or closing other agents.
- `doctor --subagent-safety` fails for the current `.codex/agents/default.toml` drift until corrected.
- Existing fixed-agent checks still pass.

## Verification

Run:

```bash
rtk .\.cowork-flow\run.cmd doctor --subagent-safety
rtk python -m pytest tests/test_cowork_agents.py -q
```
