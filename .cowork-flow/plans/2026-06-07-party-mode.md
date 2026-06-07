# Manual Party Mode Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** Add a manual Party Mode workflow that uses real subagents for bounded, evidence-based discussion and returns actionable conclusions.

**Architecture:** Implement Party Mode as a skill-first advisory workflow. The skill coordinates true child agents through the host adapter, while optional CLI support only manages report/status artifacts and stays host-neutral. Formal implement/check semantics remain owned by `cowork-implement` and `cowork-check`.

**Verification:** Targeted Python tests for skills/workflow boundaries, `doctor --subagent-safety`, `npm run test:all`, and `git diff --check`.

**Execution Strategy:** Serial. The work touches shared skills, template parity, docs, and tests; parallel slices would create high coordination overhead for little gain.

## 1. Baseline And Failing Contract Tests

**Files**

- `tests/test_cowork_agents.py`
- `tests/test_workflow_parallel_sessions.py`

**Work**

- Add failing tests that expect `party-mode` skill in root/template `.agents/skills`.
- Add failing tests for Claude mirror parity if Claude skills are expected to mirror `.agents/skills`.
- Add boundary tests that require Party Mode wording to include:
  - real child agents, not simulated personas
  - advisory-only status
  - `max_agents=3` and `max_rounds=3` as defaults, not hard-coded constants
  - configuration precedence: call arguments, task/change config, `.cowork-flow/config.yaml`, skill defaults
  - continuation and stop conditions
  - continuation and stop conditions that can be tightened but not removed
  - child and coordinator output schemas with fixed core fields and optional extensions
- Keep tests behavioral and text-contract based; avoid shallow existence-only coverage except for mirror parity.

**Verification**

```powershell
python -m unittest discover -s tests -p "test_cowork_agents.py" -v
python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py" -v
```

Expected result before implementation: targeted failures for missing Party Mode skill/contracts only.

## 2. Add Party Mode Skill

**Files**

- `.agents/skills/party-mode/SKILL.md`
- `template/.agents/skills/party-mode/SKILL.md`
- `.claude/skills/party-mode/SKILL.md`
- `template/.claude/skills/party-mode/SKILL.md`

**Work**

- Create a concise skill with:
  - trigger conditions and manual invocation wording
  - true-subagent requirement
  - round state model
  - `max_agents=3`, `max_rounds=3` as built-in defaults
  - configuration override precedence
  - configurable roster, report behavior, report path, and allowed later rounds
  - continue/stop rules as safety gates that cannot be removed
  - child output schema with required core fields and optional extensions
  - coordinator synthesis schema with required core fields and optional extensions
  - safety rules: advisory-only, no task state mutation, no child spawning
- Keep root/template copies identical.
- Mirror into Claude skills only if current sync model expects every `.agents` skill to be present there.

**Verification**

```powershell
python -m unittest discover -s tests -p "test_cowork_agents.py" -v
```

Expected result: skill set and mirror/parity tests pass.

## 3. Document Workflow Boundary

**Files**

- `README.md`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `template/.cowork-flow/spec/subagent-dispatch.md`

**Work**

- Add only the smallest necessary docs:
  - README: user-facing entry and when to use Party Mode.
  - Workflow/spec: advisory boundary if current docs do not already make it clear.
- Keep `workflow.md` host-neutral. Do not mention `spawn_agent`, `fork_turns`, or Codex-specific tool names there.
- Preserve `.cowork-flow/spec/subagent-dispatch.md` as the formal subagent protocol authority.
- Prefer short sections and stable terms over narrative explanation.

**Verification**

```powershell
python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py" -v
```

Expected result: host-neutral workflow checks and advisory boundary checks pass.

## 4. Optional CLI Report Helper

**Files**

- `.cowork-flow/scripts/party.py`
- `.cowork-flow/scripts/run.py`
- `template/.cowork-flow/scripts/party.py`
- `template/.cowork-flow/scripts/run.py`
- `tests/test_party_command.py`

**Decision Gate**

Implement this step only if the skill alone does not provide enough durable state. If implemented, the CLI must not dispatch agents.

**Work**

- Add `party` command with narrow responsibilities:
  - create a report skeleton under the active task or a named output path
  - validate report schema
  - show effective configuration when config files or call parameters are supplied
  - print next-step guidance for the skill-driven host orchestration
- Keep command host-neutral and pure Python.
- Do not call host tools, inspect live Codex agents, or mutate task status.

**Verification**

```powershell
python -m unittest discover -s tests -p "test_party_command.py" -v
```

Expected result: report helper validates schema and refuses task-state mutation.

## 5. Integrated Safety Review

**Files**

- `.agents/skills/party-mode/SKILL.md`
- `template/.agents/skills/party-mode/SKILL.md`
- `.claude/skills/party-mode/SKILL.md`
- `template/.claude/skills/party-mode/SKILL.md`
- `.cowork-flow/spec/subagent-dispatch.md`
- `README.md`
- changed tests

**Work**

- Review wording for elegance:
  - no duplicated long protocol text
  - no vague "improve discussion" phrasing
  - every boundary has a reason and a validation signal
- Review code for elegance:
  - no second scheduler
  - no hidden task-state mutation
  - no host-specific logic in host-neutral files
  - small functions and explicit schema names if CLI is added
- Confirm all PRD acceptance criteria map to tests or manual checks.

**Verification**

```powershell
.\.cowork-flow\run.cmd doctor --subagent-safety
python -m unittest discover -s tests -p "test_cowork_agents.py" -v
python -m unittest discover -s tests -p "test_workflow_parallel_sessions.py" -v
npm run test:all
git diff --check
```

Expected result: all commands pass; no unrelated files are changed.

## Risks

- Real subagent orchestration cannot be fully automated by a pure CLI; the skill must stay responsible for host-tool coordination.
- Adding Party Mode to every platform mirror can create sync drift; tests should enforce root/template/Claude parity.
- Over-documenting the protocol can make workflow docs noisy; keep deep protocol in specs and skill-local instructions.
