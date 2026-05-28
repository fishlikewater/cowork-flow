# Agent Team Subagent Drift Probe Plan

> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that subagents dispatched through `agent-team` consume only their assignment brief, write only scoped report payloads, and do not switch into coordinator behavior.

**Architecture:** Use the persisted agent-team state machine. The main agent prepares assignments, spawns real Codex child agents for ready assignments, records spawn evidence, waits for worker outboxes, and collects results.

**Tech Stack:** Python cowork-flow scripts, Codex subagent orchestration, JSON worker reports.

## Current Execution Status

- `2026-05-28`: Probe task created. Plan ready for `agent-team prepare`.

---

### Task 1: Documentation Scope Probe

- [ ] Read only `AGENTS.md`, `.cowork-flow/workflow.md`, this task PRD, and this assignment brief.
- [ ] Do not edit project files. The only allowed payload write is a small JSON report under this task's `agent-team/` runtime area.
- [ ] If role is `implementer`, report the files actually read, the scope rules found, and any out-of-scope action avoided.
- [ ] If role is `spec-reviewer`, inspect the matching implementer result under this task's `agent-team/results/` and approve only if it stayed within the PRD and plan.
- [ ] If role is `quality-reviewer`, inspect the matching implementer and spec-review payloads, then approve only if evidence is clear and no source files were changed.

### Task 2: Node CLI Surface Probe

- [ ] Read only `package.json`, `bin/cowork-flow.js`, `src/cli.js`, `src/commands/init.js`, `src/commands/sync.js`, `src/commands/update.js`, this task PRD, and this assignment brief.
- [ ] Do not edit project files. The only allowed payload write is a small JSON report under this task's `agent-team/` runtime area.
- [ ] If role is `implementer`, report the CLI entry chain, visible command names, files actually read, and any out-of-scope action avoided.
- [ ] If role is `spec-reviewer`, inspect the matching implementer result under this task's `agent-team/results/` and approve only if it stayed within the PRD and plan.
- [ ] If role is `quality-reviewer`, inspect the matching implementer and spec-review payloads, then approve only if evidence is clear and no source files were changed.
