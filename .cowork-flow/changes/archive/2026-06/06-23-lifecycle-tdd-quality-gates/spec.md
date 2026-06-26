# Lifecycle Gate Requirements

## Task Review

- Behavior-changing and bugfix tasks must not move to `review` without valid red-phase TDD evidence.
- Refactor tasks without behavior changes must name existing or characterization tests.
- Docs/chore tasks may bypass red-first TDD but must still record relevant validation evidence.

## Task Complete

- Tasks must not move to `completed` without green evidence, coding-standard evidence, and check evidence.
- Green evidence must correspond to the red command family where TDD is required.
- Missing or failed evidence must produce actionable errors.

## Test Quality

- Shallow tests must be rejected when they only assert existence, `assert True`, empty snapshots, mock calls without observable behavior, or implementation-mirroring behavior.
- Bugfix tests must identify regression input or original failure condition.

## Coding Standards

- BOM bytes in changed workflow/runtime text files must be rejected.
- Python text IO must use explicit UTF-8 encoding for text reads and writes.

## Agent Safety

- Advisory agents must not enable multi-agent features.
- `doctor --subagent-safety` and `tests/test_cowork_agents.py` must enforce the same safety rules.

## Skill And Template Sync

- TDD, check, finish-work, workflow, spec, root files, and `template/` mirrors must describe the same lifecycle contract.
