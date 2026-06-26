# Design

## Architecture

Keep `task.py` as the CLI surface and move reusable policy into small common modules:

- `quality_gate.py` validates `quality.json` and combines TDD, completion, coding-standard, and check evidence.
- `test_quality.py` rejects obvious shallow tests.
- `coding_standards.py` scans for BOM and missing explicit UTF-8 text IO.
- `agent_policy.py` centralizes fixed-agent and advisory-agent safety checks.

`task review` and `task complete` call these validators before state transitions. `doctor --subagent-safety` uses the same agent policy as tests.

## Evidence Model

Task evidence is stored under the task directory as `quality.json`. TDD-required tasks must record:

- `workType`
- `testPlan`
- `red`
- `green`
- `standards`
- `check`

Commands and captured outputs are the source of truth. Free-form AI summaries are not accepted as completion evidence.

## Skill Role

The TDD skill guides the implementation loop but does not enforce lifecycle completion. The hard guarantee remains in the validators used by `task review` and `task complete`.

## Rollout

Execute the child tasks under `.cowork-flow/tasks/06-23-lifecycle-tdd-quality-gates` serially in phase order. Each phase must update root/template copies where applicable and leave focused tests.
