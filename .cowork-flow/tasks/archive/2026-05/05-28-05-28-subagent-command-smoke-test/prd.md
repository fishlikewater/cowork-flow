# Subagent Command Smoke Test

## Goal

Verify the fixed cowork-flow agent execution contract can execute explicit read-only commands and report exact command outputs while matching the fixed-agent Codex subagent flow.

## Main Session Contract

Each fixed-agent prompt must start with:

```text
Active task: .cowork-flow/tasks/05-28-05-28-subagent-command-smoke-test
```

Each fixed agent must:

- Stay read-only.
- Run only its assigned command.
- Report the command, exit code, and relevant output.
- Avoid spawning additional agents.

## Dispatch Contract

The main session must dispatch fixed agents with Codex native subagent tools:

- `spawn_agent(agent_type="cowork-implement", fork_turns="none", message=...)`
- `spawn_agent(agent_type="cowork-check", fork_turns="none", message=...)`
- `wait_agent` to collect completion.
- `list_agents` to verify no child is left running.
- `close_agent` to close each child after completion or failure.

## Acceptance

- Subagent A executes the assigned `task current` check.
- Subagent B executes the assigned validation/search check.
- Main session records command output, exit code, and whether each child obeyed the fixed-agent contract.
- Main session closes all child agents.
