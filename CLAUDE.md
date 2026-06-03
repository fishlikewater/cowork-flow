# Claude Code Instructions

Read `AGENTS.md` first. Follow `.cowork-flow/workflow.md` and the project
specs under `.cowork-flow/spec/`.

<!-- COWORK-FLOW:START -->
Project work follows:

```text
Plan -> Implement -> Check -> Finish
```

Formal subagent dispatch uses `.claude/agents/cowork-research.md`,
`.claude/agents/cowork-implement.md`, and `.claude/agents/cowork-check.md`.
Each formal dispatch must start with `COWORK_DISPATCH_V1` or
`COWORK_DELEGATION_V1`, return `COWORK_ACK <dispatch_id> <ack_token>`, and wait
for `EXECUTE <dispatch_id>` before doing the assigned work.

If a prompt is a bounded delegated subtask, execute that prompt directly and do
not run project start/resume/archive commands unless the dispatch envelope
explicitly allows it.
<!-- COWORK-FLOW:END -->
