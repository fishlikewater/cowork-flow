# Fact-layer access

How external tools (MCP clients today, other ecosystem protocols as they
converge) and agents on hosts without injection hooks read cowork-flow task
facts. Fact-layer stage 3.

## Three channels, one fact layer

All channels consume the same services layer (`services/fact_view.py`) and
cannot drift on facts:

| Channel | Direction | Role |
|---|---|---|
| Hooks (host adapter → `inject.py`) | push | Proactive context injection; host-enforced, agents cannot skip it. |
| CLI lifecycle commands | write + pull | The only write path; enforces the full gate chain. Pull fallback when MCP is unavailable. |
| MCP tools | pull | Standardized read access for external clients (IDEs, dashboards) and hosts without hook support. |

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
inherited stdio. Outside a project the passthrough fails with a clear error;
inside one, nested subdirectories resolve to the project root.

Server info: `cowork-flow-facts`. On `initialize` the server echoes the
client's requested `protocolVersion` (falling back to `2025-06-18`).

| Tool | Input | Output | Reads |
|---|---|---|---|
| `task_state` | `{task?: string}` | The fact view as JSON text (`task`, `decisionAnchor`, `plan`, `sessions`, `snapshot`); without `task`, the session-bound active task when one resolves, or `{"task": null, "reason": "no-active-task"}` | `services/fact_view.build_fact_view` |
| `task_list` | `{}` | Active tasks overview: name, path, status, assignee, parent/children, active flag | `TaskTreeService.active_nodes` via the list records |
| `task_scope` | `{task?: string, path?: string}` | The file-scope whitelist summary, or a per-path `inScope` verdict with `path` | `services/fact_view.file_scope_whitelist` / `path_in_scope` |
| `task_specs` | `{task?: string}` | The spec/skill reading list dispatched by the task's `dev_type` | `services/fact_view.spec_entries_for_task` |

`task_scope` and `task_specs` have CLI fact-command equivalents
(`task scope`, `task specs`) consuming the same facade — MCP holds no
exclusive capability.

The MCP server process has no session concept: `task_state` without `task`
resolves the caller's session only when session identity reaches the server
through the environment (session-bound env keys). Where it cannot, it returns
`no-active-task` — pass `task` explicitly for deterministic project-level
queries. Session-bound facts remain the hook/CLI channels' responsibility.

## Registration map (two tiers)

| Host | Global (supported default) | Project-level opt-in |
|---|---|---|
| claude-code | `claude mcp add cowork-flow -- cowork-flow mcp-state` | `.mcp.json` with an `mcpServers` entry |
| zcode | user config `mcp.servers.cowork-flow = {command: cowork-flow, args: [mcp-state]}` | plugin format has no MCP field — use the global tier |
| codex | `~/.codex/config.toml` `[mcp_servers.cowork-flow]` | project config cannot enable user-approval-gated capabilities — use the global tier |
| opencode | `opencode.json` `mcp` entry | — |
| kimi-code | user config `~/.kimi-code/mcp.json` (`$KIMI_CODE_HOME/mcp.json`) `mcpServers` entry, shared across projects | `.kimi-code/mcp.json` `mcpServers` entry, effective for that repository; a same-name entry overrides the user-level one |

`run doctor` reports the registration state (project entry present, absent,
or duplicated across tiers) as an advisory, read-only health item. Registering
a new contract changes the digest fingerprint everywhere; see the change
guard.

Tool failures (unknown task, missing task.json) ride the tool result with
`isError: true`; the JSON-RPC frame stays valid.

## Change guard

- New fact sources (fields on the fact view) are additive; consumers must
  tolerate unknown keys.
- Any write-capable tool proposal must re-open this contract first — and is
  rejected by default under the current stance.
