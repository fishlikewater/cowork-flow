# 06-04-runtime-session-subagent-dispatch

## Why

Current subagent safety depends on prompt markers, entry classification, and
agent-specific wording. That creates two weak points:

- A child can see project bootstrap or no-task state before it understands its
  assigned work.
- The runtime still carries compatibility with legacy dispatch envelopes and
  ACK/EXECUTE gates, so prompts and tests keep reinforcing the old model.

The new direction is to make subagent identity a runtime fact instead of a
prompt inference. The main session creates a scoped runtime context before
spawning a child. Host hooks/plugins bind the child session to that context
before the model receives workflow state. The child then receives only its
assignment-scoped state and never runs main-session start or resume.

## Benefits

Users can dispatch weak-prompt subagents without the child being captured by
project bootstrap. Maintainers get one runtime contract shared by Codex, Claude
Code, and OpenCode instead of three sets of prompt heuristics and legacy
handshake rules.

## What Changes

1. Add runtime-context dispatch as the only formal fixed-agent dispatch model.
   The main session creates:
   - `.cowork-flow/.runtime/subagents/<runtime_context_id>.json`
   - `.cowork-flow/.runtime/sessions/subagent_<runtime_context_id>.json`

2. Bind the real child host session on first hook/plugin execution. After
   binding, the child also has:
   - `.cowork-flow/.runtime/sessions/<host_context_key>.json`

3. Replace legacy prompt protocols with a minimal runtime id transport. When a
   host cannot pass custom metadata or env, the first child prompt begins with:

   ```text
   cowork_runtime_context_id: <runtime_context_id>
   ```

4. Remove legacy formal-dispatch compatibility. The old prompt envelope,
   delegation envelope, acknowledgement, and execute-followup markers are
   removed from live code, docs, tests, templates, agents, commands, and specs.

5. Delete the former prompt-boundary skill used for subagent detection. Runtime context decides
   whether a session is main or subagent. `start` remains only as a main-session
   workflow skill with adjusted wording.

6. Sync Codex, Claude Code, and OpenCode:
   - Codex hook loads/binds runtime context from prompt/env/metadata.
   - Claude Code hook uses the same runtime resolver and binding behavior.
   - OpenCode plugin injects runtime context when `cowork_runtime_context_id`
     is present and advertises the same adapter contract.

## Non-goals

- No compatibility path for legacy dispatch envelopes.
- No downgrade to prompt-only subagent classification.
- No second long-lived workflow state machine outside `.runtime`.
- No claim that env/metadata transport exists for a host until adapter tests or
  live host verification prove it.

## Success Criteria

- A formal fixed-agent subagent can identify itself from runtime context before
  start/resume bootstrap is injected.
- Main and subagent sessions are distinguishable in `.runtime/sessions`.
- Closing a child removes its runtime session binding and marks or removes the
  transient subagent runtime context.
- Codex, Claude Code, and OpenCode adapters declare the new runtime-context
  transport and no longer declare ACK/EXECUTE contracts.
- Root and `template/` copies remain synchronized.
- Repository checks prove legacy dispatch markers are absent from live code,
  docs, tests, templates, agents, and host commands. Historical archive files
  under `.cowork-flow/changes/archive/` and `.cowork-flow/tasks/archive/` are
  out of scope and must not block this change.
