# Dashboard Runtime Control Spec

## Runtime Recording

- Formal fixed-agent runtime contexts are created through `subagent init` with `cowork-*` role or `--agent-type cowork-*`.
- When a formal runtime context has `--execution-task-dir`, the subagent runtime must resolve that path to a Flow task and create an `agent_run` row:
  - `id`: runtime context id.
  - `task_id`: resolved task id.
  - `agent_type`: resolved cowork agent type.
  - `status`: `pending`.
  - `host_context_key`: suggested child host context key.
  - `created_at`: runtime context creation timestamp.
- `subagent bind` and `subagent close` remain the source of later `bound` and `closed` status updates.
- Advisory dispatch without a Flow task must not create `agent_run`.

## Dashboard UI

- Status tab state and `显示归档` checkbox state are independent.
- The archived tab means "show archived only" and does not mutate the checkbox.
- In the all tab, archived tasks appear only when the checkbox is explicitly selected.
- Archived tasks render in a full-width history section, ordered by the API task list order, with compact metadata and status text.

## Dashboard CLI

- `dashboard` and `dashboard serve` run the HTTP server in the foreground for backward compatibility.
- `dashboard start` starts a background server for the current repository and writes `.cowork-flow/.runtime/dashboard.json`.
- `dashboard status` reports only the current repository's recorded Dashboard server.
- `dashboard stop` stops only the process recorded in the current repository runtime file and removes that runtime file when stopped.
- Runtime logs, if written, stay under `.cowork-flow/.runtime/`.
