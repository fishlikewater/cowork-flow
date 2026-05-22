# Agent Team Configured Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent-team prepare` use the project registry instead of hard-coded Codex adapter metadata.

**Architecture:** Add a small registry loader in `common/agent_team.py`, pass the registry into dispatch plan construction from `scripts/agent_team.py`, and keep existing defaults for missing values. Regression tests drive the behavior through the public `agent_team.py prepare/next` commands.

**Tech Stack:** Python standard library, unittest, existing cowork-flow scripts.

---

### Task 1: Registry-Driven Dispatch Metadata

**Files:**
- Modify: `tests/test_agent_team_plan_parser.py`
- Modify: `.cowork-flow/scripts/common/agent_team.py`
- Modify: `.cowork-flow/scripts/agent_team.py`
- Modify: `template/.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`

- [x] Step 1: Add failing regression test for customized registry.
- [x] Step 2: Run targeted test and confirm it fails before implementation.
- [x] Step 3: Implement minimal registry loading and pass it into dispatch creation.
- [x] Step 4: Run targeted tests and confirm pass.
- [x] Step 5: Run relevant Python test module set.
