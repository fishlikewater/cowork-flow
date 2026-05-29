# Clarify Parallel Planning Decision

## Goal

Clarify that users do not need to declare parallel execution when they submit a requirement. The main session evaluates parallel feasibility during the Plan stage and records the selected execution strategy in the implementation plan.

## Scope

- Update root and template workflow documentation.
- Update root and template writing-plans skill guidance.
- Add or adjust tests that lock the wording and required planning behavior.

## Acceptance Criteria

- Workflow docs state that Plan evaluates parallel feasibility and does not require user predeclaration.
- Plan guidance requires the plan to record either serial execution or explicit parallel slices.
- Tests fail if the planning docs stop carrying this rule.

## Verification

- `rtk python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py" -v`
- `rtk python -m unittest discover -s tests -p "test_*.py" -v`
- `rtk npm run test:all`
