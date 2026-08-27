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