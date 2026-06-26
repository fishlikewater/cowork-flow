# Phase 2 TDD Execution Skill

## Goal

Add a concise TDD skill that guides implementers to produce valid `quality.json` evidence without replacing lifecycle gates.

## Files

- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.claude/skills/tdd/SKILL.md`
- `template/.claude/skills/tdd/SKILL.md`
- `.cowork-flow/scripts/common/task_context_defaults.py`
- `template/.cowork-flow/scripts/common/task_context_defaults.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`

## Acceptance Criteria

- TDD skill explains `testPlan -> red -> green -> evidence` in short operational terms.
- Skill rejects shallow tests: existence-only assertions, `assert True`, empty snapshots, mock-call-only checks, and implementation-mirroring assertions.
- Skill states it is guidance only; `task review` and `task complete` are the hard gates.
- Default implementation context includes the TDD skill before coding starts.
- Root, template, and Claude-only skill mirrors are present and covered by tests.

## Verification

Run:

```bash
rtk python -m pytest tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py -q
```
