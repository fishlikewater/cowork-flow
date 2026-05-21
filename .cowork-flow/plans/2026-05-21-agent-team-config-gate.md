# Agent Team Config Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a default-disabled `agent_team.enabled` config switch that gates agent-team runtime execution.

**Architecture:** Keep the switch in `.cowork-flow/config.yaml` and parse it through the existing lightweight Python config reader. `agent_team.py` keeps `init` available, while every runtime command checks the config before touching runtime state.

**Tech Stack:** Python 3 standard library, current cowork-flow scripts, unittest, Node template sync tests.

**Current Execution Status:** Task 1 到 Task 4 已完成；`npm test`、`npm run test:template`、`npm run pack:check` 均已通过。`npm run test:template` 已改为跨平台 Node 入口，Windows 下使用 `run.cmd` 并跳过 POSIX runner 执行性测试。

---

### Task 1: Add Failing Runtime Gate Tests

**Files:**
- Modify: `tests/test_agent_team_runtime.py`
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `tests/test_agent_team_state_machine.py`

- [x] **Step 1: Add disabled-default regression tests**

Add tests proving `agent-team prepare` is blocked by default and `init` still works.

- [x] **Step 2: Update existing runtime tests to enable agent-team explicitly**

Existing tests that exercise runtime commands should write:

```yaml
agent_team:
  enabled: true
```

into `.cowork-flow/config.yaml` before calling `prepare`.

- [x] **Step 3: Run focused tests and confirm RED**

Run:

```bash
python -m unittest tests.test_agent_team_runtime tests.test_agent_team_plan_parser tests.test_agent_team_state_machine -v
```

Expected: disabled-default test fails until the runtime checks config.

---

### Task 2: Implement Config Reader and Runtime Gate

**Files:**
- Modify: `template/.cowork-flow/scripts/common/config.py`
- Modify: `.cowork-flow/scripts/common/config.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Modify: `.cowork-flow/scripts/agent_team.py`

- [x] **Step 1: Add `get_agent_team_enabled(repo_root=None)`**

The helper returns `False` unless `agent_team.enabled` is explicitly true.

- [x] **Step 2: Gate runtime commands**

Add a small wrapper in `agent_team.py` so all subcommands except `init` require the config switch.

- [x] **Step 3: Run focused tests and confirm GREEN**

Run:

```bash
python -m unittest tests.test_agent_team_runtime tests.test_agent_team_plan_parser tests.test_agent_team_state_machine -v
```

Expected: all focused tests pass.

---

### Task 3: Add Default Config and Documentation

**Files:**
- Modify: `.cowork-flow/config.yaml`
- Modify: `template/.cowork-flow/config.yaml`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `template/AGENTS.md`
- Modify: `.cowork-flow/workflow.md`
- Modify: `tests/test_agent_team_docs.py`
- Modify: `tests/test_template_convergence.py`

- [x] **Step 1: Document default-disabled config**

Add `agent_team.enabled: false` to current and template configs, and update docs to say agent-team must be enabled before plan execution can use it.

- [x] **Step 2: Add docs/template tests**

Add assertions that the template config contains `agent_team` and `enabled: false`, and docs mention enabling it.

- [x] **Step 3: Run docs/template tests**

Run:

```bash
python -m unittest tests.test_agent_team_docs tests.test_template_convergence -v
```

Expected: pass.

---

### Task 4: Final Verification and State Sync

**Files:**
- Modify: `.cowork-flow/changes/agent-team-config-gate/change.yaml`
- Modify: `.cowork-flow/tasks/<task>/prd.md`
- Modify: `.cowork-flow/tasks/<task>/*.jsonl`
- Modify: `package.json`
- Add: `scripts/run-template-tests.js`
- Add: `scripts/pack-check.js`
- Modify: `tests/test_python_runner.py`
- Modify: `.gitignore`

- [x] **Step 1: Run project verification**

Run:

```bash
npm test
npm run test:template
npm run pack:check
```

Expected: all commands pass.

- [x] **Step 2: Sync plan/task/change state**

Update this plan status, task metadata, and change metadata so they point to the final task and plan.

- [x] **Step 3: Record session and commit**

Record the session according to project policy, then commit the scoped change.
