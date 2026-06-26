# Lifecycle TDD Quality Gates Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Turn workflow guidance for TDD, coding standards, review completeness, and agent safety into machine-enforced lifecycle gates.
**Architecture:** Add a small gate kernel shared by `task.py`, `doctor.py`, and tests. Keep `task.py` as the CLI surface, but move evidence validation, coding-standard scans, TDD checks, and agent-policy checks into focused common modules mirrored in `template/`.
**Verification:** Use targeted Python tests for each gate, `doctor --subagent-safety`, `task review` / `task complete` failure-path tests, encoding/BOM scanner tests, `git diff --check`, and final `npm run test:all`.

## Execution Strategy

Serial work. These changes touch shared task lifecycle files, root/template mirrors, and overlapping tests, so parallel edits would create unnecessary merge risk.

## Scope

In scope:

- Harden `task review` and `task complete` with machine-readable evidence gates.
- Add a concise TDD execution skill so implementers know how to produce valid evidence.
- Require meaningful TDD evidence for behavior-changing and bugfix tasks.
- Reject shallow tests that do not prove behavior.
- Enforce coding standards during review and completion, not only in documentation.
- Align `doctor --subagent-safety` with existing test expectations for advisory agents.
- Keep root and `template/` copies synchronized.

Out of scope:

- Adding a new independent workflow engine or DSL.
- Making `git worktree` double-patch replay the default path.
- Reintroducing removed pattern types.
- Enforcing TDD for docs-only or pure configuration tasks.

## Task Type Policy

Use a task-level `work_type` value:

- `behavior_change`: TDD required.
- `bugfix`: TDD required with regression input.
- `refactor_no_behavior_change`: characterization or existing behavior tests required; red-first is not required.
- `docs_chore`: TDD not required; relevant validation still required.

Default unknown tasks to `behavior_change` unless explicitly marked otherwise. This is fail-closed and prevents AI from avoiding TDD by omitting classification.

## Evidence Contract

Persist lifecycle evidence under the task directory in a machine-readable file, for example `quality.json`.

Required fields for TDD-required work:

- `workType`: one of the policy values above.
- `testPlan`: each entry maps a PRD acceptance point or bug regression to a concrete test command and explains what implementation break would make it fail.
- `red`: command, exit code, failing test identifiers, captured output excerpt, and source/test diff fingerprint before production-code changes.
- `green`: command, exit code, passing test identifiers, captured output excerpt, and final diff fingerprint.
- `standards`: encoding scan, BOM scan, `git diff --check`, and shallow-test scan results.
- `check`: reviewer mode, commands run, spec-sync decision, and scope review decision.

Do not accept free-form AI claims as evidence. Commands and captured outputs are the source of truth.

## Phase 1: Shared Gate Kernel

Files:

- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_quality_gate.py`

Steps:

1. Add `GateResult` with `ok: bool`, `errors: list[str]`, and `warnings: list[str]`.
2. Add `load_quality_evidence(task_dir)` using explicit `encoding="utf-8"`.
3. Add `validate_tdd_evidence(task_dir)` for `testPlan`, `red`, and `green`.
4. Add `validate_completion_evidence(task_dir)` for final check evidence.
5. Add tests that fail when `behavior_change` lacks red evidence, when red has exit code `0`, and when green lacks a matching command.

Verification:

```bash
rtk python -m pytest tests/test_quality_gate.py -q
```

Expected result: new tests pass, and at least one test proves a missing red phase blocks completion.

## Phase 2: TDD Execution Skill

Files:

- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.claude/skills/tdd/SKILL.md`
- `template/.claude/skills/tdd/SKILL.md`
- `.cowork-flow/scripts/common/task_context_defaults.py`
- `template/.cowork-flow/scripts/common/task_context_defaults.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_host_adapters.py`

Steps:

1. Add a concise `tdd` skill that explains how to create `testPlan`, record red evidence, implement green, and reject shallow tests.
2. State explicitly that the skill guides execution only; `task review` and `task complete` remain the hard gates.
3. Add the skill to the base implementation context so every code-bearing task sees it before coding; the skill itself explains which task types require red-first TDD.
4. Keep the skill generic enough for Python and JavaScript tests, but require observable behavior assertions and command output evidence.
5. Add tests that root, `template/`, and Claude-only TDD skill mirrors exist and are included in generated implementation context when their host path is selected.

Verification:

```bash
rtk python -m pytest tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py -q
```

Expected result: the TDD skill is present in root, `template/`, and Claude-only mirrors; task context generation exposes it before implementation work.

## Phase 3: TDD Lifecycle Enforcement

Files:

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `tests/test_flow_script_paths.py`

Steps:

1. In `cmd_review`, call `validate_tdd_evidence` after pattern transition checks and before `store.update_status(..., "review", ...)`.
2. For `behavior_change` and `bugfix`, block review when `testPlan` is missing, red evidence is absent, or red command succeeded.
3. Allow `refactor_no_behavior_change` only when evidence names existing or characterization tests.
4. Allow `docs_chore` without TDD, but still require a validation entry in `quality.json`.
5. Add tests proving `task review` fails before red evidence and succeeds after valid red evidence.

Verification:

```bash
rtk python -m pytest tests/test_flow_script_paths.py -q
```

Expected result: review status cannot advance without valid evidence for behavior-changing tasks.

## Phase 4: Completion Gate Enforcement

Files:

- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/task.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_flow_script_paths.py`
- `tests/test_quality_gate.py`

Steps:

1. In `cmd_complete`, call `validate_completion_evidence` before `store.update_status(..., "completed", ...)`.
2. Require green evidence for the same command family recorded in red evidence.
3. Require coding-standard evidence and check evidence.
4. Keep pattern transition validation, but make it only one layer of the completion gate.
5. Add tests proving `task complete` fails when green evidence is missing, when standards evidence failed, and when check evidence is missing.

Verification:

```bash
rtk python -m pytest tests/test_flow_script_paths.py tests/test_quality_gate.py -q
```

Expected result: `review -> completed` is blocked until final evidence is present and passing.

## Phase 5: Shallow Test Rejection

Files:

- `.cowork-flow/scripts/common/test_quality.py`
- `template/.cowork-flow/scripts/common/test_quality.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_test_quality.py`

Steps:

1. Add a small scanner for Python and JavaScript test files changed in the task diff.
2. Reject obvious shallow assertions: `assert True`, `self.assertTrue(True)`, empty snapshots, existence-only tests, and tests that only assert a mock call without asserting observable behavior.
3. For bugfix work, require a test name or test-plan entry that includes regression input or original failure condition.
4. Keep scanner conservative: it should block clear junk tests, not attempt to prove every good test is perfect.
5. Add positive tests for behavior assertions and negative tests for shallow patterns.

Verification:

```bash
rtk python -m pytest tests/test_test_quality.py tests/test_quality_gate.py -q
```

Expected result: shallow tests are rejected, while meaningful behavior tests pass.

## Phase 6: Coding Standard Gate

Files:

- `.cowork-flow/scripts/common/coding_standards.py`
- `template/.cowork-flow/scripts/common/coding_standards.py`
- `.cowork-flow/scripts/common/quality_gate.py`
- `template/.cowork-flow/scripts/common/quality_gate.py`
- `tests/test_coding_standards.py`

Steps:

1. Add BOM byte scan for changed text files and repo workflow scripts.
2. Add Python text-IO scan for `open(`, `read_text(`, `write_text(`, and `Path.open(` calls missing explicit UTF-8 encoding when used for text.
3. Add a result format that can be embedded into `quality.json`.
4. Make `validate_completion_evidence` reject failed coding-standard evidence.
5. Document that PowerShell edits must use explicit UTF-8 and no BOM, but avoid trying to parse every shell command history.

Verification:

```bash
rtk python -m pytest tests/test_coding_standards.py tests/test_quality_gate.py -q
rtk git diff --check
```

Expected result: BOM and missing-encoding regressions are blocked by tests and gate logic.

## Phase 7: Agent Policy Gate

Files:

- `.cowork-flow/scripts/common/agent_policy.py`
- `template/.cowork-flow/scripts/common/agent_policy.py`
- `.cowork-flow/scripts/doctor.py`
- `template/.cowork-flow/scripts/doctor.py`
- `tests/test_cowork_agents.py`

Steps:

1. Move fixed-agent and advisory-agent safety rules into `agent_policy.py`.
2. Make `doctor --subagent-safety` use the same policy checks as tests.
3. For advisory agents `worker`, `default`, and `explorer`, require `multi_agent = false`, `features.multi_agent_v2.enabled = false`, and explicit prohibition on spawning or coordinating agents.
4. Preserve existing fixed-agent checks.
5. Add or adjust tests so `.codex/agents/default.toml` drift to `multi_agent = true` fails through both test and doctor paths.

Verification:

```bash
rtk .\.cowork-flow\run.cmd doctor --subagent-safety
rtk python -m pytest tests/test_cowork_agents.py -q
```

Expected result: doctor and tests agree on advisory-agent safety drift.

## Phase 8: Workflow And Skill Contract Sync

Files:

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

Steps:

1. Update workflow text to state that TDD and coding-standard gates are machine-enforced.
2. Update review and completion state templates so agents know missing evidence blocks state transitions.
3. Update check and finish-work skills to inspect `quality.json` and reject shallow tests.
4. Ensure the TDD skill points to machine evidence and does not become a bypass around lifecycle gates.
5. Keep root/template wording aligned.
6. Add tests that guard the new mandatory snippets in root and template files.

Verification:

```bash
rtk python -m pytest tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py tests/test_patterns.py -q
```

Expected result: docs, skills, and template contract tests all match the new lifecycle behavior.

## Phase 9: Integrated Verification

Commands:

```bash
rtk python -m pytest tests/test_quality_gate.py tests/test_test_quality.py tests/test_coding_standards.py tests/test_flow_script_paths.py tests/test_cowork_agents.py tests/test_workflow_parallel_sessions.py tests/test_host_adapters.py -q
rtk .\.cowork-flow\run.cmd doctor --subagent-safety
rtk git diff --check
rtk npm run test:all
```

Expected result:

- All targeted Python tests pass.
- `doctor --subagent-safety` blocks advisory-agent drift and passes on corrected config.
- `git diff --check` reports no whitespace or line-ending failures.
- `npm run test:all` passes for the full project gate.

## Rollout Notes

- Fix the existing `.codex/agents/default.toml` advisory-agent drift as part of Phase 7, not as an unrelated cleanup.
- Keep the first implementation minimal: JSON evidence file plus shared validators is enough. Do not add a new DSL.
- Keep `git worktree` double-patch replay as an optional future diagnostic for disputed TDD evidence, not the default gate.
- When the gate blocks a transition, print actionable errors naming the missing evidence field and the command that should produce it.
- Keep the TDD skill short. The hard guarantee must live in validators, not in long instructional text.

## Acceptance Criteria

- `task review` fails for `behavior_change` and `bugfix` tasks without valid red evidence.
- `task complete` fails without green evidence, coding-standard evidence, and check evidence.
- The TDD skill is present in root, `template/`, and Claude-only mirrors, and implementation context generation exposes it before coding starts.
- Shallow tests are rejected by the quality gate.
- Coding-standard violations are rejected by the completion gate.
- `doctor --subagent-safety` and `tests/test_cowork_agents.py` enforce the same advisory-agent safety rules.
- Root and `template/` copies remain synchronized for runtime, workflow, and skill contract changes.
- The final integrated verification commands all pass.
