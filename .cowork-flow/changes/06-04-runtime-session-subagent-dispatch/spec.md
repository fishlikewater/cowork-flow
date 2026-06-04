# Runtime-context subagent dispatch spec

## 1. Formal dispatch identity

Formal `cowork-research`, `cowork-implement`, and `cowork-check` dispatch must
use runtime context identity.

The parent must create a unique `runtime_context_id` before spawning a child.
The child must resolve that id through host metadata, env, structured hook
input, or prompt text before any main-session workflow state is injected.

Legacy dispatch markers and ACK/EXECUTE handshakes are not valid formal
dispatch inputs.

## 2. Runtime storage

The runtime must distinguish main and subagent sessions:

- Main sessions use `.cowork-flow/.runtime/sessions/<main_context_key>.json`
  with `scope: "main"`.
- Subagent dispatch creates
  `.cowork-flow/.runtime/subagents/<runtime_context_id>.json`.
- Subagent dispatch also creates
  `.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`.
- On first child hook/plugin execution, the runtime creates or updates
  `.cowork-flow/.runtime/sessions/<host_context_key>.json` with
  `scope: "subagent"` and the same `runtime_context_id`.

Subagent sessions must not inherit the parent session file.

## 3. Hook/plugin behavior

Hooks/plugins must resolve runtime context in this order:

1. Host metadata key `cowork_runtime_context_id`.
2. Env key `COWORK_FLOW_RUNTIME_CONTEXT_ID`.
3. Structured hook input key `cowork_runtime_context_id`.
4. Prompt line `cowork_runtime_context_id: <id>`.

If a valid runtime context is found, the hook/plugin must:

- Bind the current host context key to the runtime context.
- Inject `delegated_subtask` workflow state.
- Include assignment, role, task dir, allowed context, and forbidden actions.
- Skip main active-task lookup and main start/resume state.

If the id is missing, invalid, expired, or points to a closed context, formal
dispatch must fail closed. It must not fall back to prompt classification or
legacy dispatch protocols.

## 4. Host adapter requirements

Adapter declarations must expose runtime context dispatch capabilities:

- `runtimeContextDispatch`
- `runtimeContextBinding`
- `runtimeContextCleanup`
- `stateInjection`
- `freshChildContext`
- `dispatchSubagent`
- `waitChild`
- `listChildren`
- `cancelChild`

Adapters must declare the active transport:

- `prompt`
- `env`
- `metadata`
- `plugin`

Prompt transport must use:

```text
cowork_runtime_context_id: <runtime_context_id>
```

Env and metadata transport may be enabled only after host-specific verification
or adapter tests prove support.

## 5. Child authority

A bound subagent has leaf-executor authority only:

- It may read the task, PRD, context files, and assignment-scoped files.
- It may edit only files allowed by the assignment.
- It may run validation commands allowed by the assignment.
- It must not run task start, unscoped resume, task finish, task archive,
  commit, push, spawn, wait, list, or cancel agents.

Runtime command gates must reject subagent sessions for coordinator-only
operations.

## 6. Close and cleanup

Closing a child must:

- Remove `.runtime/sessions/<host_context_key>.json`.
- Remove `.runtime/sessions/subagent_<runtime_context_id>.json`.
- Delete `.runtime/subagents/<runtime_context_id>.json` or mark it `closed`
  until TTL GC removes it.
- Leave durable evidence only in task/report/test/git artifacts.

Stale pending contexts must be garbage-collected.

## 7. Skill and doc cleanup

The former prompt-boundary skill is removed from root, Claude Code, and
template skill trees.
`start` remains only as a main-session workflow skill.

Live code, docs, tests, templates, agents, commands, hooks, plugins, current
change/task artifacts, and adapter specs must not contain the legacy formal
dispatch markers used by the old prompt envelope, delegation envelope,
acknowledgement, or execute-followup flow.

Historical archive files under `.cowork-flow/changes/archive/` and
`.cowork-flow/tasks/archive/` are explicitly out of scope.
