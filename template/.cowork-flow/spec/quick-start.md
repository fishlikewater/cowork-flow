# Quick Start — Cowork Flow

> 1-page index for new readers. The rules live in `core/`; details in `reference/`.

## Minimal workflow

```
changes → brainstorming → read spec → plan → tasks → implement → check → complete
```

1. **changes**: Capture the raw requirement in `.cowork-flow/changes/`.
2. **brainstorming**: Align on goal, scope, acceptance criteria, rejected options.
3. **read spec**: Read relevant contracts in `core/`.
4. **plan**: Write `.cowork-flow/plans/YYYY-MM-DD-<slug>.md` with verification commands.
5. **tasks**: Create tasks under `.cowork-flow/tasks/`, write `prd.md`, `implement.jsonl`, `check.jsonl`.
6. **implement**: Dispatch `cowork-implement` (fixed agent, leaf executor).
7. **check**: Dispatch `cowork-check` (fixed agent, leaf executor).
8. **complete**: Final verification, spec sync, archive, session recording, commit.

## When to read what

| You are... | Read these first |
| --- | --- |
| Setting up cowork-flow for the first time | This file + `core/lifecycle.md` |
| Implementing a feature | `core/lifecycle.md` + `core/dispatch.md` |
| Adding a host adapter | `core/dispatch.md` + `reference/adapters/capabilities.md` + `reference/adapters/adapter.schema.json` |
| Implementing a new pattern | `core/lifecycle.md` + `reference/patterns/index.md` |
| Configuring Party Mode | `reference/party-mode-v2-board.md` |
| Writing code (Python/JS) | `reference/guides/pre-implementation-checklist.md` + language-specific guidelines (`reference/backend/` for Python, `reference/frontend/` for JS) |

## Core protocol (must obey)

All rules below are mandatory. Violations break the fail-closed safety chain.

- **`core/entry.md`** — Entry classification: structured signal > legacy fallback > fail-closed.
- **`core/dispatch.md`** — Formal subagent dispatch via runtime context.
- **`core/lifecycle.md`** — Task lifecycle, fixed agents, state machine.
- **`core/state-templates.md`** — Workflow state text injected by hooks/plugins.

## Reference (details, read as needed)

- **`reference/patterns/`** — Pattern contracts (generic, fan-out, pipeline, human-loop).
- **`reference/adapters/`** — Host capability declarations and adapter schema.
- **`reference/party-mode-v2-board.md`** — Party Mode V2 board protocol.
- **`reference/guides/`** — Thinking guides (code reuse, cross-layer thinking, pre-implementation checklist).
- **`reference/backend/`** — Backend development guidelines (Python, CLI, runtime scripts).
- **`reference/frontend/`** — Frontend development guidelines (JS/TS, dashboard, web assets).

## Quick commands

```bash
# Task lifecycle
./.cowork-flow/run task create "<title>" --slug <slug>
./.cowork-flow/run task start <task-dir>
./.cowork-flow/run task review [task-dir]
./.cowork-flow/run task complete [task-dir]
./.cowork-flow/run task archive <task-name>
./.cowork-flow/run task next [task-dir]

# Subagent dispatch
./.cowork-flow/run subagent init
./.cowork-flow/run subagent spawn-family <parent-task>

# Dashboard
./.cowork-flow/run dashboard start
./.cowork-flow/run dashboard stop

# Migration
./.cowork-flow/run flow migrate --dry-run
./.cowork-flow/run flow migrate --status
```

## Task levels

| Level | Description | Flow |
| --- | --- | --- |
| L0 | No external behaviour change (docs, formatting, refactor) | `brainstorming` → `read spec` → `implement` → `check` → `complete` |
| L1 | Local behaviour change | Full 8-step flow |
| L2 | Cross-layer / significant change | Full flow + cross-layer check + readiness gate |

## Safety

- **Fail-closed**: `UNKNOWN` entry classification blocks workflow mutation.
- **Fixed agents are leaves**: They cannot dispatch other agents.
- **Runtime context is the source of truth**: Formal subagent identity comes from DB, not from prompt text.
