# Context injection protocol

Single source for how every host adapter injects cowork-flow runtime context
into a session: the transport shape, the event timing matrix, the contract
digest shape rules (full block vs fingerprint line), and the fingerprint
serialization norm. All host implementations — zcode JS hook, the Python
shared core (codex / claude-code / dsh), and the opencode JS plugin — must
follow this document; cross-host behavior tests lock the three independent
implementations to it.

This document is a meta-protocol: it describes the injection layer itself and
is intentionally **not** registered in `contract-registry.json` (registering it
would make the digest self-referential).

## Transports

| Host | Transport | Shape |
|---|---|---|
| zcode | process hook (`inject-context.js`), stdout JSON | `hookSpecificOutput.{hookEventName, additionalContext}` |
| codex | command hook (Python shell), stdout JSON | same shape |
| claude-code | command hook (Python shell), stdout JSON | same shape |
| opencode | plugin `experimental.chat.system.transform` + `shell.env` | system-prompt section push / env object |
| dsh | preset plugin system-prompt section | named section, replace semantics |

The string block inside every transport follows the same shape: an optional
runtime preamble, the contract digest (full block or fingerprint line, see
below), optional `decision-anchor` / `stage-contract` blocks, and the
`<workflow-state>` block. It is **not** byte-identical across hosts at the
string level — the digest policy line differs per host wording and zcode
drops the registry-warning line. Exactly two things are byte-identical and
test-locked: the contract digest **fingerprint value** and the
`<stage-contract>` block.

| Host | workflow-state emission | digest policy line wording |
|---|---|---|
| zcode | always (main + delegated) | `policy: repeat fingerprint every hook; read full spec files only before listed actions.` |
| codex / claude-code / dsh (Python core) | always (main + delegated) | `policy: repeat this short digest every hook; read full spec files only before listed actions.` |
| opencode | delegated subagent sessions only | `policy: repeat this short digest every plugin transform; read full spec files only before listed actions.` |

The opencode plugin has no ordinary-session injection channel: its
`shell.env`/transform coverage is scoped to delegated subagent sessions, and
the in-memory session set re-injects the full digest after a process restart
(deliberate, see "Change guard").

## Event timing matrix

Each host signals "session start" differently (or not at all). The digest
shape depends on this signal; the fallback for hosts without a session-start
event is the session state file probe.

| Host | Session-start signal | Mid-session refresh | Shape derivation |
|---|---|---|---|
| zcode | `SessionStart` hook event (startup / clear / compact) | PostToolUse on lifecycle commands | event name: SessionStart → full; otherwise fingerprint |
| claude-code | `SessionStart` hook event | — | event name from hook input: SessionStart → full; otherwise fingerprint |
| opencode | none (transform only) | every prompt assembly | in-memory per-session set: first injection full, later fingerprint |
| codex | none (`UserPromptSubmit` only) | — | session state file probe: no activation file → full; file present → fingerprint |
| dsh | `agent/session-start`, `agent/inbox/claimed` | `tools/result` on lifecycle commands | refresh source: session-start events → full; tools/result → fingerprint |

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
zcode / codex / claude-code / dsh; the opencode line covers delegated
subagent sessions only.

## Workflow-state structured header (stage 1)

The `<workflow-state>` open tag carries the machine-readable fact header as
XML attributes; the body keeps the human-readable breadcrumb prose.

- Attributes: `status` and `source` are always present; `task` (repo-relative
  task path) appears whenever a task is bound. Attribute values are XML-escaped
  (`& < > "`).
- The legacy `Task:` / `Status:` / `Source:` label lines are gone — machines
  parse the attributes, humans read the body. There is no bare `Scope:`
  line in the body: the stage-contract block owns the scope declaration
  (main sessions render the boundary as `[agent-mutable]`; delegated sessions
  as a read-only `[read-only]` reference of the parent task).

```text
<workflow-state task=".cowork-flow/tasks/08-28-demo" status="in_progress" source="runtime-session">
活动任务正在执行。...
</workflow-state>
```

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
Rejected: <rejected option name>; ...             (first 6 names)
</decision-anchor>
```

- Extracted from `decision-anchor.md` with the line-level parser frozen in
  `services/fact_view.py` (`parse_decision_anchor`); the zcode and opencode JS
  lines carry an identical parser shape.
- Missing anchor file, no extractable essentials, or terminal statuses
  (`completed`) inject nothing.

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
Gates: edits outside Scope are review blockers; CLAUDE.md and workflow files are protected; spec/ edits may be allowed by review policy; scope is agent-mutable (self-declared via task context add)
Verify: npm run test:fast; python3 -m pytest tests/ -q
</stage-contract>
```

- **Scope**: the task's file-scope whitelist (file/planned-file/deleted-file
  entries; directory entries and non-canonical paths — `..` segments,
  absolute paths, drive letters, wildcards, unsupported types — authorize
  nothing and are dropped, matching `context_paths.normalize_context_file_scope_entry`),
  first 8 + `(+N more)`. The scope is **agent-mutable** on main
  (`task context add` can extend it) — it is a self-declared boundary, not a
  hard fence; the label says so. Delegated sessions inherit the parent
  task's scope and see it as `[read-only]` — the child must not believe it
  can self-declare scope on the parent's behalf.
- **Specs**: `.cowork-flow/spec/` pointer entries from implement.jsonl
  (first 4, same canonicality filter as Scope). Read them before coding; the
  full files are not injected.
- **Gates**: static preview text, identical on all hosts; the delegated
  variant replaces the self-declaration sentence with "scope is inherited
  from the parent task (read-only reference)".
- **Verify**: `## 验证命令` lines from decision-anchor (first 3, 120 chars
  each) — the agent's own declared self-checks; omitted when none.
- **Per-edit warning (zcode only)**: PostToolUse on Edit/Write/MultiEdit
  injects at most one line when the edited file is outside the scope
  (`editScopeWarning: plugin`; every other host declares `unsupported` —
  their fallback is this static stage-contract preview). Bash-initiated
  writes (redirection, tee) are a declared residual gap: the warning covers
  Edit/Write/MultiEdit tool invocations only. The PostToolUse matcher text
  (`Bash|Edit|Write|MultiEdit`) is asserted by template tests but depends on
  the ZCode runtime's tool names — there is no external runtime contract to
  verify them against, so a runtime rename would silently disable the
  warning; the matcher is the single switch.
- Budget: the whole block stays ≤ 1200 characters. Over-budget inputs
  degrade by dropping Verify, then Specs, then shrinking Scope entries
  (min 1) — the closing tag and the Gates row always survive; tests assert
  the block stays well-formed. The scope-filter rules and the stage-contract
  budget/limits come from `.cowork-flow/spec/runtime/scope-rules.json`, the
  single source consumed by Python and both JS mirrors at runtime; a missing
  or malformed file degrades to embedded defaults that are byte-identical
  with the shipped file (locked by `tests/test_scope_rules.py`).
- Absent for `no_task` / `planning` / `completed` states. Block content is
  byte-identical across the three host implementations for the whole fixture
  matrix (`test/fixtures/stage-contract-matrix.json` drives the cross-host
  equality test: canonical, `./`-prefixed, invalid-boundary, over-budget,
  emoji, missing-anchor, empty-scope, delegated-readonly). The JS scope
  filter is a port of the Python rules and is locked by that matrix — a
  port, not a mechanism, so the matrix list grows whenever the rules grow.

The authoritative per-file verdict lives in the MCP `task_scope` tool
(`services.fact_view.file_scope_whitelist` — same semantics, live data).

## Fingerprint computation

sha256 over (1) the registry `contracts` array serialized with
**recursively sorted keys** (Python `json.dumps(..., sort_keys=True,
ensure_ascii=False)`; the JS implementations use the equivalent
`stableStringify`), then (2) each contract file's raw bytes in registry
order; a missing file hashes as the literal string `missing:<path>`. The
fingerprint is the first 16 hex chars of the digest.

Serialization must be byte-identical across the three implementations: same
key order, same escaping (ASCII-safe content), same UTF-8 encoding. The
cross-host test (`test/contract-fingerprint.test.js`) asserts this and is the
regression lock against drift.

## Change guard

- Any change to a registered contract file, or to the registry's `contracts`
  array, must change the fingerprint everywhere (same value on all hosts).
- Hosts without `SessionStart` support must keep the "first injection after
  task activation is full" fallback so a resuming session still receives the
  full contract listing at least once.