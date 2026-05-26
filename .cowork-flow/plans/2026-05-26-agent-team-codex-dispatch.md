# Agent Team Codex Dispatch Implementation Plan

> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agent-team parse current writing-plans task headings and align Codex dispatch guidance with the official subagent documentation and observed runtime behavior.

**Architecture:** Keep `agent-team` as a coordinator-dispatched runtime: Python generates assignments and state, while the main agent asks Codex to spawn child agents through natural-language orchestration prompts. The runtime must treat visible child-thread evidence as the success condition, rather than trusting final-answer wording.

**Tech Stack:** Python standard library, unittest, Markdown skill documentation.

## Current Execution Status

- `2026-05-26`: Parser compatibility for `## Task N:` and `### Task N:` implemented in root and template runtimes.
- `2026-05-26`: Final-verification terminal-task dependency rule implemented so end-state tasks do not become first-batch ready.
- `2026-05-26`: `agent-team-execution` rewritten to use official Codex natural-language orchestration wording, plus a subagent evidence gate that blocks false-positive recording when no child-thread evidence exists.
- `2026-05-26`: Real Codex experiments run with `codex exec --json` showed no child-agent events for the standard `Spawn one explorer agent...` prompt under the current runtime/provider, so the skill now requires explicit runtime evidence before `record-result` / `record-review`.
- `2026-05-26`: Verification passed with `npm run test:all`.

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

### Task 2: Document Codex Dispatch Protocol

**Files:**
- Modify: `tests/test_agent_team_docs.py`
- Modify: `.agent/skills/agent-team-execution/SKILL.md`
- Modify: `template/.agent/skills/agent-team-execution/SKILL.md`

- [x] **Step 1: Write failing documentation regression test**

Assert root and template `agent-team-execution` skills describe fresh worker dispatch, worker result handling, Codex orchestration wording, `agent_type` / `recommended_agent` usage, and the runtime evidence boundary for true subagent execution.

- [x] **Step 2: Run test and verify failure**

Run: `python3 -m unittest tests.test_agent_team_docs.AgentTeamDocsTest.test_agent_team_execution_skill_uses_codex_subagent_orchestration_language -v`

Expected before implementation: fail because the skill still described deprecated literal tool names or lacked the evidence gate.

- [x] **Step 3: Update skill instructions**

State that agent-team should use official Codex natural-language orchestration prompts, map `agent_type` to real Codex agent names, and require visible child-thread or job evidence before recording assignment outcomes.

- [x] **Step 4: Run test and verify pass**

Run: `python3 -m unittest tests.test_agent_team_docs.AgentTeamDocsTest.test_agent_team_execution_skill_uses_codex_subagent_orchestration_language -v`

Expected after implementation: pass.
