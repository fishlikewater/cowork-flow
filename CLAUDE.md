# Claude Code Instructions

Follow `.cowork-flow/workflow.md` and the project specs under
`.cowork-flow/spec/`.

<!-- COWORK-FLOW:START -->
@AGENTS.md

Project work follows:

```text
Plan -> Implement -> Check -> Finish
```

Formal subagent dispatch uses `.claude/agents/cowork-research.md`,
`.claude/agents/cowork-implement.md`, and `.claude/agents/cowork-check.md`.
Project workflow skills are exposed under `.claude/skills/`; Claude Code does
not auto-load `.agent/skills`.
`.claude/settings.json` registers `UserPromptSubmit` and `SessionStart` hooks
that inject cowork-flow workflow state and the short contract digest.
Each formal dispatch must create a runtime context with
`.cowork-flow/run subagent init` and pass
`cowork_runtime_context_id: <runtime_context_id>` to the child. The child hook
binds that id before workflow-state injection. Missing, closed, invalid, or
mismatched runtime context is fail-closed.

If the current thread is a bound subagent, execute only the assigned leaf task.
Do not run project start/resume/archive commands, commit, push, or invoke other
agents.
<!-- COWORK-FLOW:END -->
