# Phase 8 Workflow And Skill Contract Sync

## Goal

Synchronize workflow docs, lifecycle specs, state templates, and skills with the new machine-enforced gate model.

## Files

- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.cowork-flow/spec/core/lifecycle.md`
- `template/.cowork-flow/spec/core/lifecycle.md`
- `.cowork-flow/spec/core/state-templates.md`
- `template/.cowork-flow/spec/core/state-templates.md`
- `.agents/skills/check/SKILL.md`
- `template/.agents/skills/check/SKILL.md`
- `.agents/skills/finish-work/SKILL.md`
- `template/.agents/skills/finish-work/SKILL.md`
- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.claude/skills/tdd/SKILL.md`
- `template/.claude/skills/tdd/SKILL.md`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`
- `tests/test_patterns.py`

## Acceptance Criteria

- Workflow text states TDD and coding-standard gates are machine-enforced.
- Review and completion state templates say missing evidence blocks state transitions.
- Check and finish-work skills inspect `quality.json` and reject shallow tests.
- TDD skill points to machine evidence and cannot be used as a lifecycle bypass.
- Root/template wording remains aligned and guarded by tests.

## Verification

Run:

```bash
rtk python -m pytest tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py tests/test_patterns.py -q
```
