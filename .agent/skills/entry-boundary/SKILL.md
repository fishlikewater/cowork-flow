---
name: entry-boundary
description: Use before project start/resume in cowork-flow projects to decide whether the current message is a top-level user request or a delegated subtask, and route delegated/uncertain work to scoped recovery instead of full project context loading.
---

# Entry Boundary

Use this before `.agent/skills/start` or any full project `resume`.

## Classify

Classify the current message as exactly one:

Classify the actual user or delegation task message, not project bootstrap text such as AGENTS.md, environment_context, or injected instruction blocks. Bootstrap text constrains behavior, but it is not the task being classified.

- `MAIN_SESSION`: the user is directly asking this agent to work in this repository, or explicitly says `not a subagent`, `main agent`, or `run full cowork-flow start`.
- `DELEGATED_SUBTASK`: the message is delegated work. Strong signals include `you are a subagent`, `delegated subtask`, `dispatched worker`, `Assignment ID`, `child thread`, `you are explorer`, `you are worker`, `you are reviewer`, `only investigate`, `do not modify files`, or a bounded report format such as `return/output findings`.
- `UNCERTAIN`: neither side is clear.

Delegated signals override main-session signals. If a prompt contains a concrete task, working directory, commands, and output format, treat it as `DELEGATED_SUBTASK` even when repository `AGENTS.md` also mentions top-level start/resume rules.

When in doubt, choose `UNCERTAIN`. This avoids pulling a delegated subtask into the main coordinator workflow.

## Delegation Marker

cowork-flow dispatchers SHOULD put this marker at the top of spawned child prompts when they control the prompt shape:

```text
origin: spawn_agent
scope: bounded
main-start: forbidden
assignment-source: this prompt
```

The marker is a strong signal, not the only signal. Other tools may dispatch subtasks without it; classify those by the bounded task shape above.

For `DELEGATED_SUBTASK`, the assignment prompt is the first source of truth. Project rules may constrain how work is done, but they must not replace the assigned goal with main-session recovery.

## Route

### MAIN_SESSION

Run `.agent/skills/start` and follow the normal cowork-flow project workflow.

### DELEGATED_SUBTASK with scoped context

Do not run `.agent/skills/start` and do not run unscoped `./.cowork-flow/run resume`.
Recover only the subtask scope:

```bash
./.cowork-flow/run --context-file <context.json> resume
```

### DELEGATED_SUBTASK without scoped context

Do not run `.agent/skills/start`.
Create scoped recovery state for this delegated task, then continue only within that recorded scope:

```bash
./.cowork-flow/run subagent init --title "<short title>" --role <role> --goal "<assigned goal>"
```

Add `--allowed-context <path>` for any prompt-named files the subtask may read.

### UNCERTAIN

Do not run full start/resume. Use safe-read only, or create a generic subagent context if the assigned scope is clear enough. Ask for clarification only if the boundary cannot be recovered from the prompt.

## Output Shape

Keep the decision short:

```text
Boundary: MAIN_SESSION | DELEGATED_SUBTASK | UNCERTAIN
Action: run start | scoped resume | subagent init | safe-read only
Reason: <one or two signals>
```

## Rules

- This skill is a routing gate, not a project context loader.
- A `DELEGATED_SUBTASK` is a leaf executor by default: execute the assignment in this prompt directly. Do not call spawn_agent, wait_agent, close_agent, or list_agents, and do not wait for another subagent, unless the assignment explicitly says coordinator or asks you to manage other agents.
- Delegated or uncertain work must not activate tasks, run coordinator mutation commands, or load main-session resume context.
- Scoped recovery is allowed and expected for delegated subtasks; the boundary prevents only main coordinator recovery.
