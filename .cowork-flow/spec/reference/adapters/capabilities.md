# Host capabilities

`cowork-flow` uses capability declarations to decide whether a host can run formal fixed-agent workflow steps directly or needs a fallback. Capabilities are enums, not booleans, so an adapter can state how stable the support is.

## Values

| Value | Meaning |
| --- | --- |
| `native` | Host exposes the capability as a first-class primitive. |
| `shim` | Adapter can emulate the capability with host primitives. |
| `plugin` | Capability requires a host plugin or hook. |
| `external` | Capability requires a separate command or service. |
| `experimental` | Capability exists but must not be default workflow behavior. |
| `unsupported` | Capability is unavailable. |

## Required capabilities

- `dispatchSubagent`: create a child agent for formal workflow work.
- `freshChildContext`: start child with bounded context, not inherited full session history.
- `runtimeContextDispatch`: create a runtime context before child dispatch.
- `runtimeContextBinding`: bind the host child session to that runtime context
  through a proven hook/plugin path or an explicit first-step shim.
- `runtimeContextCleanup`: close child runtime DB sessions and mark runtime context closed.
- `spawnMultipleSubagents`: host can dispatch several prepared child contexts
  for a Fan-out family.
- `waitMultipleChildren`: host can wait for or inspect several children during
  Fan-out family closeout.
- `sendFollowup`: send follow-up instructions when the host supports it.
- `waitChild`: wait for child result.
- `listChildren`: inspect active children.
- `cancelChild`: stop an incorrect or cancelled child.
- `stateInjection`: inject workflow or runtime state before task recovery.
- `backgroundChild`: run a child while the main session continues.

Formal `cowork-research`, `cowork-implement`, and `cowork-check` require
`dispatchSubagent`, `freshChildContext`, `waitChild`, `runtimeContextDispatch`,
`runtimeContextBinding`, and `runtimeContextCleanup`. If a required capability
is `unsupported`, the adapter must use `fallback.whenRequiredCapabilityMissing`.

## Project-root anchored commands

Host assets that execute cowork-flow commands must not assume their current
working directory is the project root unless that host contract explicitly
guarantees it. Runtime context remains stored in the DB `runtime_context` row;
host assets must not describe `.cowork-flow/.runtime/subagents/*.json` as an
active state authority.

Claude Code hook, command, fixed-agent, and skill assets must anchor executable
cowork-flow commands with `CLAUDE_PROJECT_DIR`:

```bash
${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run python ${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/inject-workflow-state.py
${CLAUDE_PROJECT_DIR:-.}/.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>
```

Tests protect this through `tests/test_claude_hooks.py`,
`tests/test_host_adapters.py`, `tests/test_cowork_agents.py`,
`tests/test_subagent_dispatch.py`, `doctor --host-adapters`, and
`doctor --subagent-safety`.
