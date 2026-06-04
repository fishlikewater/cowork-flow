# Runtime Session Subagent Dispatch

**Goal:** Replace prompt/protocol-based subagent dispatch with runtime-context
identity for Codex, Claude Code, and OpenCode.

**Execution strategy:** Inline main-session work. This changes the subagent
runtime itself, so fixed-agent dispatch should not be used until the new runtime
context path is implemented and verified.

**Verification:** Focused Python/Node tests for runtime context creation,
hook/plugin binding, adapter schema, root/template sync, absence of legacy
protocol strings outside historical archives, then `npm run test:all`.

## Steps

### Sequential Tasks

1. `.cowork-flow/tasks/06-04-runtime-context-data-model`
2. `.cowork-flow/tasks/06-04-runtime-context-hook-binding`
3. `.cowork-flow/tasks/06-04-runtime-dispatch-contract-cleanup`
4. `.cowork-flow/tasks/06-04-runtime-dispatch-verification`

1. Finalize L2 design artifacts.
   - Verify: change has proposal/spec/design, plan link, task link, and PRD.

2. Add runtime context model.
   - Verify: tests show `subagent init` creates `.runtime/subagents/<id>.json`,
     `.runtime/sessions/subagent_<id>.json`, and returns
     `cowork_runtime_context_id`.

3. Bind child sessions in hooks/plugins.
   - Verify: Codex and Claude hook tests resolve prompt/env/metadata ids and
     inject `delegated_subtask` before main active-task lookup; OpenCode plugin
     test injects the same runtime state.

4. Update host adapters and schema.
   - Verify: adapter schema accepts runtime context transport fields and rejects
     legacy ACK/EXECUTE contract fields.

5. Remove legacy protocols and the former prompt-boundary skill.
   - Verify: prompt-boundary skills are deleted in root, Claude Code, and
     template; `start` is main-session-only; agents/commands no longer mention
     legacy dispatch strings.

6. Add close and cleanup behavior.
   - Verify: tests show child close removes host and logical subagent session
     files and stale pending contexts are garbage-collected.

7. Run integrated checks.
   - Verify: focused tests, sync tests, legacy-string absence check excluding
     `.cowork-flow/changes/archive/` and `.cowork-flow/tasks/archive/`,
     `git diff --check`, and `npm run test:all`.
