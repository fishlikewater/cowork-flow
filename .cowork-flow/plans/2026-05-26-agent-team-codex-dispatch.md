# Agent Team Codex Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agent-team parse current writing-plans task headings and clearly require real Codex subagent dispatch when multi-agent support is enabled.

**Architecture:** Keep `agent-team` as a coordinator-dispatched runtime: Python generates assignments and state, while the main agent performs Codex `spawn_agent` / `wait_agent` / `close_agent` calls. Parser compatibility is a minimal regex change applied to both project and template copies.

**Tech Stack:** Python standard library, unittest, Markdown skill documentation.

**Current Execution Status:** Task 1 and Task 2 implemented; change validation and agent-team regression tests passed.

---

### Task 1: Accept Two-Hash Task Headings

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`

- [x] **Step 1: Write failing regression test**

Add a test that rewrites the sample plan headings from `### Task` to `## Task` and expects `agent-team prepare` to generate `T001-implementer`, `T002-implementer`, and `T003-implementer`.

- [x] **Step 2: Run test and verify failure**

Run: `python3 -m unittest tests.test_agent_team_plan_parser.AgentTeamPlanParserTest.test_prepare_accepts_two_hash_task_headings -v`

Expected before implementation: fail with `unable to parse plan tasks`.

- [x] **Step 3: Implement minimal parser compatibility**

Change the task heading regex from `^### Task` to `^#{2,3} Task` in both runtime copies.

- [x] **Step 4: Run test and verify pass**

Run: `python3 -m unittest tests.test_agent_team_plan_parser.AgentTeamPlanParserTest.test_prepare_accepts_two_hash_task_headings -v`

Expected after implementation: pass.

### Task 2: Document Codex Spawn-Agent Protocol

**Files:**
- Modify: `tests/test_agent_team_docs.py`
- Modify: `.agent/skills/agent-team-execution/SKILL.md`
- Modify: `template/.agent/skills/agent-team-execution/SKILL.md`

- [x] **Step 1: Write failing documentation regression test**

Assert root and template `agent-team-execution` skills mention `spawn_agent`, `wait_agent`, `close_agent`, `multi_agent`, and the manual fallback boundary.

- [x] **Step 2: Run test and verify failure**

Run: `python3 -m unittest tests.test_agent_team_docs.AgentTeamDocsTest.test_agent_team_execution_skill_requires_codex_spawn_agent_when_available -v`

Expected before implementation: fail because the skill only says to dispatch ready assignments generically.

- [x] **Step 3: Update skill instructions**

State that Codex with `[features] multi_agent = true` must dispatch ready assignments with `spawn_agent`, collect results with `wait_agent`, and call `close_agent`; manual fallback is allowed only when those tools are unavailable.

- [x] **Step 4: Run test and verify pass**

Run: `python3 -m unittest tests.test_agent_team_docs.AgentTeamDocsTest.test_agent_team_execution_skill_requires_codex_spawn_agent_when_available -v`

Expected after implementation: pass.
