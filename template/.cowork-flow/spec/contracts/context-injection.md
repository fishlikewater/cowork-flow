# Context injection protocol

Single source for how every host adapter injects cowork-flow runtime context
into a session: the transport shape, the event timing matrix, the contract
digest shape rules (full block vs fingerprint line), and the fingerprint
serialization norm. The workflow facts are rendered by ONE Python source —
`adapters/host/inject.py` over `workflow_state_hook.py` +
`services.fact_view.py` — consumed by every declared host: the zcode
transport shim (node), the opencode plugin transform shim, claude-code,
codex, dsh, kimi-code, and qoder.

This document is a meta-protocol: it describes the injection layer itself and
is intentionally **not** registered in `contract-registry.json` (registering it
would make the digest self-referential).

## Transports

| Host | Transport | Shape |
|---|---|---|
| zcode | process hook shim (`inject-context.mjs`) → `inject.py --host zcode`, stdout JSON | `hookSpecificOutput.{hookEventName, additionalContext}` |
| codex | thin wrapper (`inject-workflow-state.py`) → `inject.py --host codex`, stdout JSON | same shape |
| claude-code | thin wrapper (`inject-workflow-state.py`) → `inject.py --host claude-code`, stdout JSON | same shape |
| opencode | plugin `experimental.chat.system.transform` → shim (`cowork-flow/plugin-core.js`) → `inject.py --host opencode`, bare-text stdout | system-prompt section push; `shell.env` exports the context key to shell commands |
| dsh | preset plugin system-prompt section | named section, replace semantics |
| kimi-code | user-level `config.toml` (`$KIMI_CODE_HOME`, default `~/.kimi-code/`) `[[hooks]]` row on `UserPromptSubmit` → shim (`cowork-flow-inject.mjs`) → `inject.py --host kimi-code` | bare-text stdout appended to the prompt context, no `hookSpecificOutput` envelope |
| qoder | machine-level plugin `hooks/hooks.json` (node, `${QODER_PLUGIN_ROOT}/hooks/inject-context.mjs`) → project `.cowork-flow/scripts/.../inject.py --host qoder`, stdout JSON | `hookSpecificOutput.{hookEventName, additionalContext}` plus a top-level `systemMessage` (a CLI-visible trace; the model context is unchanged) |

The qoder row carries one delta beyond the shared envelope: `systemMessage`,
emitted only on the two injecting events (`SessionStart`, `UserPromptSubmit`)
and rendered from the same task-state resolution as the injected block, so the
message can never report a state other than the one just injected. It exists
because an injection is otherwise invisible to the user. The message reaches a
user only on the CLI side: the interactive TUI renders it as
`<hook name> says: <text>`, and an ACP session sends the SessionStart message
straight to the client as an agent-message chunk. The Qoder desktop client
(1.1.64) renders no hook output text at all — it has no `systemMessage` /
`hook_system_message` string, its chat renderer drops hook parts, and it drives
the worker over `--output-format stream-json` rather than ACP; there the hook's
only trace is the hook-summary tooltip on the assistant reply. Every other host
keeps the envelope unchanged, and tests assert none of them carries the key.

Kimi Code registers that one `UserPromptSubmit` row and nothing else: the
other events — `SessionStart`, `PostToolUse` — are observe-only, their stdout
is discarded, so only a blockable event can inject and `UserPromptSubmit` is
the sole channel.

Exit-status contract, split by install scope. The machine-level shims (Qoder,
ZCode, Kimi Code, OpenCode) are **fail-open**: they run in every workspace, so
they meet project runtimes older than themselves, and a project-side failure — an
argparse rejection of the host argument, a crash, a timeout — must not fail the
event they only decorate. Each keeps the child's message on stderr (the host's
run log) and completes the event with nothing injected. Exit-status blocking is reserved
for the project-level edit gate (`spec_only_post_tool_use`, installed by
`init` / `sync` for claude-code and codex): that wrapper sits next to the
runtime it calls, so hook and runtime cannot skew.

The string block inside every transport follows the same shape: an optional
runtime preamble, the contract digest (full block or fingerprint line, see
below), optional `decision-anchor` / `stage-contract` blocks, and the
`<workflow-state>` block. It is **not** byte-identical across hosts at the
string level — the digest policy line differs per host wording and zcode
drops the registry-warning line; both differences are selected inside the
single Python source by `--host`. Exactly two things are byte-identical and
test-locked: the contract digest **fingerprint value** and the
`<stage-contract>` block.

| Host | workflow-state emission | digest policy line wording |
|---|---|---|
| zcode | always (main + delegated) | `policy: repeat fingerprint every hook; read full spec files only before listed actions.` |
| codex / claude-code / kimi-code / dsh / qoder (Python core) | always (main + delegated) | `policy: repeat this short digest every hook; read full spec files only before listed actions.` |
| opencode | always (main + delegated) | `policy: repeat this short digest every plugin transform; read full spec files only before listed actions.` |

The opencode transform fires on every prompt assembly, so its main sessions
receive the same workflow-state block as every other host; the wording keeps
"every plugin transform" because the plugin has no hook-event vocabulary of
its own.

## Host identity resolution

Every host's session identity facts live in ONE declaration,
`runtime/host_identity.py` (`HOST_IDENTITIES`): the context-key prefix, the
adapter label, the policy module, the per-session environment variables, the
hook-payload keys, and the optional process label. `inject.py`,
`workflow_state_hook.py`, `session_state.py` and `subagent.py` derive their
tables from it. Adding a host is one row plus, optionally, its policy module.

### Resolution order

`resolve_context_key_with_provenance` resolves in this order; the first hit wins.

| # | Source | Provenance |
|---|---|---|
| 1 | env `COWORK_FLOW_CONTEXT_ID` | `explicit` |
| 2 | env, each host's `session_env` in registry order | `host_session` |
| 3 | payload `COWORK_FLOW_CONTEXT_ID` / `cowork_flow_context_id` / `context_id` | `explicit` |
| 4 | payload keys of the resolved host | `host_session` |
| 5 | the host's `process_label_env` | `process_fallback` |
| 6 | nothing matched | `missing` |

### Key ownership is derived, not declared

A host lists every payload key it may emit, ambiguous ones included; listing a
key truthfully is what makes the derivation correct. A key resolves without
host evidence only while a single host declares it:

| Key | Declarers | Resolvable without host evidence |
|---|---|---|
| `sessionID` | opencode | yes |
| `thread_id`, `conversation_id`, `*_session_id`, `*_SESSION_ID` | one each | yes |
| `session_id` | codex, zcode, claude-code, kimi-code | no |
| `sessionId` | opencode, zcode | no |

A key becomes ambiguous the moment a second host lists it, so no one has to
remember to re-file it. No host may rewrite payload keys to claim one either:
a host's declared key list is the only reading rule, and the per-host payload
aliases that predated this contract were retired.

### Declared-host channel

`inject.py` stamps `COWORK_FLOW_HOST=<host id>` into the hook payload, taken
from its required `--host` argument, before rendering; the resolver then never
infers a host from key shapes. `COWORK_FLOW_HOST` may also be set in the
environment for the Bash/CLI side. Kimi Code has no such environment: its Bash
tool exports no session variable and its hook payload carries only the generic
`session_id`, so the CLI side reads the injected `session="kimi_<id>"` header
and must pass `COWORK_FLOW_CONTEXT_ID` (or `COWORK_FLOW_HOST=kimi-code`)
explicitly. With a known host, every key that host declares is interpretable,
ambiguous ones included. A declared host id that is not registered fails
closed — no identity — and an unknown host never inherits another host's
prefix. Callers that bypass `inject.py` (the dsh preset plugin) pass
`hook_input` directly or stay on their own env identity.

### Degradation invariant

When no host evidence exists and the payload carries only ambiguous keys, the
identity is `missing`; a host that cannot establish an identity degrades rather
than borrowing another's. Locked by
`tests/test_active_task_runtime.py::test_context_key_generic_session_id_requires_declared_host`
(previously a bare `session_id` resolved as a codex session).

### Prefix table

Prefixes are the registry's `prefix` field and `platform_from_context_key`
maps back through the same table (unknown prefix → `manual`). `claude-code`
uses the prefix `claude`, a historical quirk preserved verbatim.
`injects_context` marks the hosts that route through `inject.py` and is exactly
the `--host` choice set; every declared host routes there today, and the flag
stays so a future host can opt out explicitly.

Host ids are also mirrored in `.cowork-flow/spec/runtime/host-assets.json`,
which owns asset layout. The two lists are locked together by
`tests/test_host_identity.py::test_registry_ids_match_host_asset_manifest`;
that mirror is the only remaining duplication and it is test-guarded.

## Event timing matrix

Each host signals "session start" differently (or not at all). The digest
shape depends on this signal; the fallback for hosts without a session-start
event is the session state file probe.

| Host | Session-start signal | Mid-session refresh | Shape derivation |
|---|---|---|---|
| zcode | `SessionStart` hook event (startup / clear / compact) | PostToolUse on lifecycle commands | event name: SessionStart → full; otherwise fingerprint |
| claude-code | `SessionStart` hook event | — | event name from hook input: SessionStart → full; otherwise fingerprint |
| opencode | none (transform only) | every prompt assembly | session state file probe: no activation file → full; file present → fingerprint |
| codex | none (`UserPromptSubmit` only) | — | session state file probe: no activation file → full; file present → fingerprint |
| dsh | `agent/session-start`, `agent/inbox/claimed` | `tools/result` on lifecycle commands | refresh source: session-start events → full; tools/result → fingerprint |
| kimi-code | none (`UserPromptSubmit` only) | — | session state file probe: no activation file → full; file present → fingerprint |

## Digest shape rules

Two shapes, both sha256-based:

1. **Full block** — `<cowork-runtime host=… adapter=…>` wrapping
   `<contract-digest fingerprint="…">` with the policy line, per-contract
   `path` / `digest` (first 2) / `read_before` lines, and the closing tags.
   Emitted when the session-start signal fires (event or activation-file
   probe) — i.e. the session may not have seen the contract listing yet.

2. **Fingerprint line** — single
   `<contract-fingerprint value="…"/>`. Emitted for every other injection
   (mid-session messages, post-lifecycle refreshes) so long sessions do not
   pay the full listing on every message. The policy line wording differs per
   host line (see the transport table); the fingerprint *value* is
   byte-identical everywhere.

The `<workflow-state>` block is emitted independently of digest shape on
zcode / codex / claude-code / dsh / kimi-code / opencode.

## Workflow-state structured header (stage 1)

The `<workflow-state>` open tag carries the machine-readable fact header as
XML attributes; the body keeps the human-readable breadcrumb prose.

- Attributes: `status` and `source` are always present; `task` (repo-relative
  task path) appears whenever a task is bound; `session` (the caller's
  resolved context key) appears whenever a session identity is resolvable
  from the hook input or environment and is omitted otherwise (hosts that
  cannot resolve an identity never guess one — the attribute is the machine
  handle for re-binding with `COWORK_FLOW_CONTEXT_ID`). Attribute values are
  XML-escaped (`& < > "`).
- The legacy `Task:` / `Status:` / `Source:` label lines are gone — machines
  parse the attributes, humans read the body. There is no bare `Scope:`
  line in the body: the stage-contract block owns the scope declaration
  (main sessions render the boundary as `[agent-mutable]`; delegated sessions
  as a read-only `[read-only]` reference of the parent task).

```text
<workflow-state task=".cowork-flow/tasks/08-28-demo" status="in_progress" source="runtime-session" session="zcode_probe">
An active task is in progress. ...
</workflow-state>
```

- Unbound-session fallback (zcode only, display/warning-only): a hook
  session with no binding follows another main session's binding only while
  **exactly one** main-session binding exists (`source="session-fallback"`).
  With two or more main-session bindings the newest one belongs to some
  other window, so the fallback refuses: the injection renders
  `status="no_task"` plus the rebind hints list. The CLI lifecycle commands
  keep their strict identity semantics regardless (FALLBACK_BINDING_BLOCKER).

## Decision-anchor injection (stage 1)

For tasks whose status is `planning`, `in_progress`, or `review` (a delegated
subtask reads the underlying task's status), hosts with the task bound also
inject a compact `<decision-anchor task="...">` block before
`<workflow-state>`, so every session knows why the task exists and what done
means without re-reading the file:

```text
<decision-anchor task=".cowork-flow/tasks/08-28-demo">
Goal: <first goal line, max 160 chars>
Acceptance: AC-001 <text, max 80>; AC-002 <...>   (first 8 items)
AC evidence: <with evidence>/<total>[ missing=<id,...>, max 5]
Rejected: <rejected option name>; ...             (first 6 names)
</decision-anchor>
```

- Extracted from `decision-anchor.md` with the line-level parser frozen in
  `services/fact_view.py` (`parse_decision_anchor`) — the only parser; every
  host line renders through it.
- The `AC evidence:` row appears only for tasks that declare AC rows, right
  after the `Acceptance:` row, and renders byte-identically across the
  python / zcode-shim lines (matrix-locked); the opencode transform spawns
  the same Python entry, so its bytes are identical by construction (render-
  tested in `test/opencode-plugin.test.js`). Schema and gate semantics live
  in `evidence-completion.md`.
- Missing anchor file, no extractable essentials, or terminal statuses
  (`completed`) inject nothing.

## Stage contract (implementation guardrails)

For tasks whose effective status is `in_progress` or `review`, hosts with
the task bound also inject a compact `<stage-contract task="...">` block
after `<decision-anchor>`, so the implementing agent sees its edit boundary,
the specs to read, and what the gates will check — before coding, not at
review time:

```text
<stage-contract task=".cowork-flow/tasks/08-30-demo">
Scope: src/demo.py; src/next.py (+1 more in implement.jsonl) [agent-mutable]
Specs: .cowork-flow/spec/backend/index.md (+1 more)
Gates: edits outside Scope are review blockers; CLAUDE.md and workflow files are protected; spec/ edits may be allowed by review policy; scope is agent-mutable (declare more in implement.jsonl)
Verify: npm run test:fast; python3 -m pytest tests/ -q
</stage-contract>
```

- **Scope**: the task's file-scope whitelist (file/planned-file/deleted-file
  entries; directory entries and non-canonical paths — `..` segments,
  absolute paths, drive letters, wildcards, unsupported types — authorize
  nothing and are dropped, matching `context_paths.normalize_context_file_scope_entry`),
  first 8 + `(+N more)`. The scope is **agent-mutable** on main
  (appending a scope entry to `implement.jsonl` extends it) — it is a
  self-declared boundary, not a hard fence; the label says so. Delegated
  sessions inherit the parent
  task's scope and see it as `[read-only]` — the child must not believe it
  can self-declare scope on the parent's behalf.
- **Specs**: `.cowork-flow/spec/` pointer entries from implement.jsonl
  (first 4, same canonicality filter as Scope). Read them before coding; the
  full files are not injected. Once the task is `in_progress`, the line
  upgrades to `Specs: <spec>(<h2 heading tree>); …`: at most 6 h2 entries,
  each truncated to 24 characters with `();` characters stripped; a missing
  file adds no annotation. The digest is an entry-name index, not the prose,
  and is hard-capped by `scope-rules.json` `stageContract.budget`; over
  budget the whole line yields. The python/zcode output comes from a single
  Python entrypoint, locked by the `test/stage-contract.test.js` matrix;
  opencode transports that same entrypoint's output, so byte-exact equality
  holds by construction.
- **Gates**: static preview text, identical on all hosts; the delegated
  variant replaces the self-declaration sentence with "scope is inherited
  from the parent task (read-only reference)".
- **Verify**: `## 验证命令` lines from decision-anchor (first 10, 120 chars
  each) — the agent's own declared self-checks; omitted when none.
- **Per-edit warning**: PostToolUse on an edit tool injects at most one
  line when the edited file is outside the task's declared scope —
  a frozen single line shared by every host, differing only in transport:
  zcode / claude-code / codex / qoder return it as
  `hookSpecificOutput.additionalContext`, opencode (bare-text `emit_text`)
  appends it to the finished tool output, and dsh attaches it to the tool
  result as a plugin notice. `editScopeWarning: plugin` is declared for
  those six hosts; kimi-code declares `unsupported` because the host drops
  PostToolUse stdout. Silence rules: no active in_progress/review task, a
  subagent session, an in-scope path, or no extractable path; every failure
  stays silent and every host exits 0 — the edit has already happened. No
  host refreshes the workflow-state digest from this hook: the advisory is
  the whole payload (state refreshes on the next injecting event, or on
  dsh's `tools/result`).
  Bash-initiated writes (redirection, tee) are a declared residual gap: the
  warning covers edit tool invocations only. Each host's matcher text
  (`Edit|Write|MultiEdit`, codex's `apply_patch|Write|Edit`, qoder's
  `Edit|Write`) is asserted by template tests but depends on that host's
  runtime's tool names — there is no external runtime contract to verify
  them against, so a runtime rename would silently disable the warning; the
  matcher is the single switch.
- Budget: the whole block stays ≤ 3400 characters. Over-budget inputs
  degrade by dropping Verify, then Specs, then shrinking Scope entries
  (min 1), then truncating the Scope row's own text. The opening tag, the
  closing tag and the Gates row always survive intact — a body-wide cut
  would either truncate the tag every consumer matches on (making the block
  invisible to them) or silently drop the edit-policy row, so neither is
  allowed. Below the size those fixed rows plus a minimal `Scope: X` row
  need, or when the cut would shave a `Scope: ` label off any row, the block
  is returned whole and may exceed the budget: guard rows and parseability
  outrank the budget.
  The scope-filter rules and the stage-contract
  budget/limits come from `.cowork-flow/spec/runtime/scope-rules.json`, the
  single source consumed at runtime; a missing or malformed file degrades to
  embedded defaults that are byte-identical with the shipped file (locked by
  `tests/test_scope_rules.py`). The file is template-managed
  (`syncPolicy.safeFiles`): `cwf project sync` refreshes it, so local edits to
  it do not survive a sync.
- Absent for `no_task` / `planning` / `completed` states. Block content is
  byte-identical across host lines for the whole fixture matrix
  (`test/fixtures/stage-contract-matrix.json` drives the equality test:
  canonical, `./`-prefixed, invalid-boundary, over-budget, emoji,
  missing-anchor, empty-scope, delegated-readonly). Both JS-delivered lines
  (zcode hook shim, opencode plugin transform) run through the same Python
  source as the python line, so the matrix locks python/zcode and the
  opencode line inherits the bytes by construction.

The authoritative per-file verdict lives in the MCP `task_scope` tool
(`services.fact_view.file_scope_whitelist` — same semantics, live data).

## Fingerprint computation

sha256 over (1) the registry `contracts` array serialized with
**recursively sorted keys** (Python `json.dumps(..., sort_keys=True,
ensure_ascii=False)`), then (2) each contract file's raw bytes in registry
order; a missing file hashes as the literal string `missing:<path>`. The
fingerprint is the first 16 hex chars of the digest.

The computation lives only in the Python source. The cross-host test
(`test/contract-fingerprint.test.js`) locks the zcode shim against it, and
the opencode render tests pin the value the transform injects, so no second
implementation can drift.

## Change guard

- Any change to a registered contract file, or to the registry's `contracts`
  array, must change the fingerprint everywhere (same value on all hosts).
- Hosts without `SessionStart` support must keep the "first injection after
  task activation is full" fallback so a resuming session still receives the
  full contract listing at least once.