# Agent Registry Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agents.yaml` fields, especially custom prompts, actually affect agent-team dispatch and generated assignment prompts.

**Architecture:** Extend the existing lightweight registry parser to support scalar fields, list fields, nested risk limits, and `prompt: |` blocks without adding dependencies. Use deterministic scoring to select configured agents for the existing implement/review assignment phases, then carry the selected prompt into dispatch data and rendered assignment markdown.

**Tech Stack:** Python standard library, unittest.

---

## Current Status

- Change/spec/task context created.
- Implementation and verification complete.

### Task 1: Add Failing Tests for Runtime Consumption

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`

- [x] Step 1: Add a test where `agents.yaml` defines a custom implementation agent with `capabilities`, `preferred_task_types`, `file_patterns`, `agent_type`, and `prompt: |`; `prepare` must select that agent and include its prompt in `assignments/T001-implementer.md`.
  Verification: targeted unittest fails before implementation.

- [x] Step 2: Add a test proving `codex_type` is ignored when `agent_type` is absent.
  Verification: targeted unittest fails before implementation because current runtime still reads `codex_type`.

### Task 2: Implement Registry Parsing and Prompt Rendering

**Files:**
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`
- Modify: `.cowork-flow/scripts/common/agent_team.py`

- [x] Step 3: Parse `agent_type`, `capabilities`, `preferred_task_types`, `file_patterns`, `risk_limits.max_parallel_write_conflicts`, and multiline `prompt`.
- [x] Step 4: Remove `codex_type` fallback.
- [x] Step 5: Select configured agents using deterministic role/task/file scoring.
- [x] Step 6: Include agent prompt in assignment data, status data, and rendered assignment markdown.

### Task 3: Update Default Agents

**Files:**
- Modify: `template/.cowork-flow/agent-team/agents.yaml`
- Modify: `.cowork-flow/agent-team/agents.yaml`
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Modify: `.cowork-flow/scripts/agent_team.py`

- [x] Step 7: Add default prompts to common agents and add useful default roles such as tester, debugger, docs-agent, and release-reviewer.
- [x] Step 8: Keep init defaults aligned with template config.

### Task 4: Verify and Sync

**Files:**
- Check: `tests/test_agent_team_plan_parser.py`
- Check: `tests/test_agent_team_runtime.py`
- Check: `tests/test_template_convergence.py`

- [x] Step 9: Run `python3 -m unittest tests.test_agent_team_plan_parser tests.test_agent_team_runtime tests.test_template_convergence`.
- [x] Step 10: Run `python3 -m unittest tests.test_agent_team_docs tests.test_agent_team_state_machine tests.test_agent_team_runtime`.
- [x] Step 11: Sync task/change/plan/session state before handoff.

## Optional fields regression

- [x] Added and verified `test_prepare_treats_agent_registry_fields_as_optional` so missing optional agent fields do not fail prepare.
