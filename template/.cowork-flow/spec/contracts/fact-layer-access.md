# Fact-layer access

How external tools (MCP clients today, other ecosystem protocols as they
converge) read cowork-flow task facts. Stage 3 of `docs/direction.md`.

## Stance

- **Read-only access here.** Writes flow exclusively through the CLI
  lifecycle commands (`run task ...`), which enforce the full gate chain —
  planning artifacts, file-scope whitelist, executor ownership. An MCP write
  path would bypass that governance and is therefore out of scope.
- **No homegrown cross-agent protocol.** The transport is whatever the
  ecosystem standardizes; today that is MCP. Adapters stay thin: one server
  file per protocol, delegating to the same fact layer (`services/fact_view.py`,
  `run state --json`).
- **Dependency-free.** The MCP stdio transport is newline-delimited JSON-RPC
  2.0, served by `adapters/mcp/state_server.py` on the standard library. A
  heavyweight SDK dependency is deferred until the ecosystem settles.

## MCP server

Command: `./.cowork-flow/run mcp-state` (stdio, one JSON-RPC message per
line; notifications are never answered; unknown methods return `-32601`;
stderr is kept log-only).

Global registration: `cowork-flow mcp-state` (npm CLI) resolves the nearest
`.cowork-flow/` from the client's cwd and execs that project's runner with
inherited stdio — register it once (`command: cowork-flow, args:
["mcp-state"]`) and every cowork-flow project works, because the root
resolution is identical to the server's own (`get_repo_root`). Outside a
project the passthrough fails with a clear error; inside one, nested
subdirectories resolve to the project root.

Server info: `cowork-flow-facts`. On `initialize` the server echoes the
client's requested `protocolVersion` (falling back to `2025-06-18`).

| Tool | Input | Output | Reads |
|---|---|---|---|
| `task_state` | `{task?: string}` | The fact view as JSON text (`task`, `decisionAnchor`, `plan`, `sessions`, `snapshot`); without `task`, the session-bound active task, or `{"task": null, "reason": "no-active-task"}` | `services/fact_view.build_fact_view` |
| `task_list` | `{}` | Active tasks overview: name, path, status, assignee, parent/children, active flag | `TaskTreeService.active_nodes` via the list records |

Tool failures (unknown task, missing task.json) ride the tool result with
`isError: true`; the JSON-RPC frame stays valid.

## Change guard

- New fact sources (fields on the fact view) are additive; consumers must
  tolerate unknown keys.
- Any write-capable tool proposal must re-open this contract first — and is
  rejected by default under the current stance.