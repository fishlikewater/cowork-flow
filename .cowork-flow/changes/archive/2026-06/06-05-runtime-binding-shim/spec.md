# Runtime Binding Shim Spec

## 1. Adapter capability truth

### 1.1 Codex binding capability

Given Codex uses `spawn_agent` for formal subagent dispatch
When runtime context binding is declared in `.cowork-flow/adapters/codex/adapter.yaml`
Then `runtimeContextBinding` must not be `native` unless a real child-session
smoke proves automatic hook binding updates `bound_context_key`.

### 1.2 Three-host binding mode

Given Codex, Claude Code, and OpenCode all support formal `cowork-*` agents
When an adapter cannot prove model-before-execution automatic binding
Then the adapter must support explicit shim binding by prompt command.

## 2. Shim bind prompt contract

### 2.1 Required prompt fields

Given a main session dispatches `cowork-research`, `cowork-implement`, or
`cowork-check`
When it creates a runtime context
Then the child prompt must include:

- `cowork_runtime_context_id: <runtime_context_id>`
- `cowork_host_context_key: <host_context_key>`
- a first-step `subagent bind <runtime_context_id> <host_context_key>` command.

### 2.2 Bind before work

Given a formal child receives a prompt with runtime context fields
When it starts execution
Then it must run the bind command before reading broad task context, editing
files, checking diff, or reporting success.

### 2.3 Bind failure behavior

Given bind fails because the context is missing, closed, invalid, mismatched, or
already bound to another key
When the child observes that failure
Then it must report `needs_context` and stop without executing role work.

## 3. Runtime bind semantics

### 3.1 Successful bind

Given `.cowork-flow/.runtime/subagents/<id>.json` exists with `scope=subagent`
and is not closed
When `subagent bind <id> <host_context_key>` succeeds
Then it must write a session file under
`.cowork-flow/.runtime/sessions/<host_context_key>.json`
And it must update runtime context to:

- `status=bound`
- `bound_context_key=<host_context_key>`
- `last_seen_at=<timestamp>`

### 3.2 Idempotent same-key bind

Given a runtime context is already bound to `<host_context_key>`
When the same bind command runs again
Then it should succeed without changing the binding target.

### 3.3 Different-key bind rejection

Given a runtime context is already bound to `<host_context_key_a>`
When a bind command tries `<host_context_key_b>`
Then it must fail unless an explicit force/cleanup path is introduced.

## 4. Parent acceptance

### 4.1 Bound state required

Given the main session dispatches a formal child
When it waits for child completion or checks health
Then it must verify runtime context is bound before accepting role output.

### 4.2 No text-only success

Given a child final response says it completed
When runtime context remains `pending` or `bound_context_key=null`
Then the parent must treat the dispatch as not formally accepted.

### 4.3 Cleanup

Given a child completes, fails, or is cancelled
When the parent closes the dispatch
Then `subagent close <runtime_context_id>` must remove bound session files and
mark runtime context `closed`.

## 5. Host assets

### 5.1 Fixed agent definitions

Given root and template host assets exist for Codex, Claude Code, and OpenCode
When this change is implemented
Then every formal fixed-agent definition must mention:

- required `cowork_runtime_context_id`
- required `cowork_host_context_key`
- first-step bind command
- fail-closed behavior when bind fails
- leaf executor prohibition on spawning/waiting/listing/closing agents

### 5.2 Command templates

Given host command assets describe how to dispatch formal agents
When this change is implemented
Then command text must tell the main session to generate a runtime context,
generate a host context key, pass both to the child, wait, verify bound runtime
state, and close runtime context.

## 6. Tests

Implementation must add or update tests for:

- direct hook/plugin binding still injects delegated state;
- explicit shim bind succeeds;
- same-key bind is idempotent;
- different-key bind is rejected;
- Codex adapter no longer overstates native binding;
- Codex, Claude Code, and OpenCode root/template agent assets include the shim
  bind contract.
