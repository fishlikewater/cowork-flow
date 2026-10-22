# <Feature> Implementation Plan

> Execution rule: this plan exists to prevent implementation drift. The implementer must work through tasks in order.
> If the plan conflicts with current code facts, a plan-external file becomes necessary, or a test fails for an unplanned reason, stop and report back instead of expanding scope.
>
> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

| Field | Content |
|----|------|
| **Task Type** | Tiny / Normal / High-risk: <reason> |
| **Strategy** | Serial / Parallel: <why> |
| **Success Criteria** | AC-001 / AC-002 / AC-003 |
| **Final Verification** | `<command>` -> exit 0; clause-by-clause check against applicable `.cowork-flow/spec/<dev_type>/` rules and project gates -> `pass` / `not_applicable` per clause |
| **Primary Risk** | Low / Medium / High: <one sentence> |

**Goal:** <One sentence describing the observable behavior change>

## Goal

<1-3 sentences describing the expected observable behavior.>

## Acceptance Criteria

- AC-001: <observable behavior>
- AC-002: <observable behavior>

## Global Constraints

- <Architecture boundary, compatibility requirement, command, or output field that must be preserved>
- <Explicitly prohibited scope expansion>

## File Boundaries

- `path/a.py`: <responsibility; only change this function or region>
- `tests/test_a.py`: <responsibility; only add or modify these tests>

## Tasks

Tiny plans may keep a shorter brief, but must still name exact file boundaries, completion conditions, and one verification command.

### Task N: <small goal>

**Purpose**
- <Observable behavior after this task is complete>

**Code Fact Sources**
- Read: `path/a.py::function_name`
- Read: `tests/test_a.py::test_existing_behavior`

**File Boundaries**
- Create / Modify / Test: `path/a.py` (only change <function/region>)
- Test: `tests/test_a.py` (only change <test/region>)

**Key Symbols**
- Change: `function_name()`, `ClassName.method()`, `<config-key>`
- Preserve: `existing_helper()`, output field `<field>`

**Implementation Notes**
```python
# Core control-flow sketch; adjust names to match existing code.
# Do not copy a complete implementation into the plan.
...
```

**Test Proof**
- `tests/test_a.py::test_x`: proves <specific behavior>
- Core assertion: <one sentence describing the assertion, not only the test name>

**Verification Command**
```bash
<command>
```

When changed files are covered by `.cowork-flow/spec/<dev_type>/` rules, add the deciding command or a spec/gate check line (`pass` / `not_applicable` with reason) here; it is a strong review reminder, not a hard gate.

**Completion Conditions**
- <2-4 checkable conditions>

**Prohibited Drift**
- <2-5 explicit prohibited changes>

**Deviation Conditions**
- If <plan-external file/layer> becomes necessary, must stop and report back because the file boundary is wrong.

## Final Verification

```bash
<command>
```

Spec check: clause-by-clause check against applicable `.cowork-flow/spec/<dev_type>/` rules -> <pass / not_applicable + reason>.
