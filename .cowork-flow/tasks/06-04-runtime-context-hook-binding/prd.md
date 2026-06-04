# Runtime Context Hook Binding

## Goal

Bind child sessions to runtime contexts before workflow state injection for
Codex, Claude Code, and OpenCode.

## Scope

- `.codex/hooks/inject-workflow-state.py`
- `.claude/hooks/inject-workflow-state.py`
- `.opencode/plugins/cowork-flow.js`
- Template mirrors
- Hook/plugin tests

## Non-goals

- No runtime data-model schema changes beyond using helpers from the previous
  task.
- No agent/skill/spec cleanup in this task.
- No edits to historical archive files.

## Acceptance Criteria

- Hooks/plugins resolve `cowork_runtime_context_id` from metadata, env,
  structured input, and prompt text.
- A valid runtime context injects `delegated_subtask` state and skips main
  active-task lookup.
- Invalid runtime ids fail closed and do not fall back to old dispatch markers.
- Codex, Claude Code, and OpenCode root/template copies stay in sync.

## Verification

- `python -m unittest tests.test_codex_hooks tests.test_claude_hooks`
- Focused OpenCode plugin test if present or added
- `git diff --check`
