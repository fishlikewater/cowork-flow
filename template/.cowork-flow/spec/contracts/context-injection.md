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

The string block inside every transport is structurally identical across
hosts: an optional runtime preamble, the contract digest (full block or
fingerprint line, see below), and the `<workflow-state>` block.

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
   pay the full listing on every message. `policy: repeat fingerprint every
   hook; read full spec files only before listed actions.`

The `<workflow-state>` block is always emitted, independent of digest shape.

## Workflow-state structured header (stage 1)

The `<workflow-state>` open tag carries the machine-readable fact header as
XML attributes; the body keeps the human-readable breadcrumb prose.

- Attributes: `status` and `source` are always present; `task` (repo-relative
  task path) appears whenever a task is bound. Attribute values are XML-escaped
  (`& < > "`).
- The legacy `Task:` / `Status:` / `Source:` label lines are gone — machines
  parse the attributes, humans read the body. `Scope: subagent` style context
  lines stay in the body.

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
  entries; directories authorize nothing), first 8 + `(+N more)`. The scope
  is **agent-mutable** (`task context add` can extend it) — it is a
  self-declared boundary, not a hard fence; the label says so.
- **Specs**: `.cowork-flow/spec/` pointer entries from implement.jsonl
  (first 4). Read them before coding; the full files are not injected.
- **Gates**: static preview text, identical on all hosts.
- **Verify**: `## 验证命令` lines from decision-anchor (first 3, 120 chars
  each) — the agent's own declared self-checks; omitted when none.
- Budget: the whole block stays ≤ 1200 characters (asserted by tests).
- Absent for `no_task` / `planning` / `completed` states. Byte-identical
  across the three host implementations (cross-host equality test).

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