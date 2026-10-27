# Security policy

[中文](SECURITY.md) | English

## Supported versions

Only the latest minor series is maintained; the current line is `2.x`. Security fixes go into the next patch version, and earlier minors are not backported. The current published version is whatever [npm](https://www.npmjs.com/package/cowork-flow) serves; see [CHANGELOG.md](CHANGELOG.md) for historical versions.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: **Security → Advisories → Report a vulnerability** in the repository (<https://github.com/fishlikewater/cowork-flow/security/advisories/new>). Do not open a public issue.

Please state the affected command and version, reproduction steps, and the actual impact you observed. This is a hobby project without commercial support, so there is no response-time commitment; confirmed problems are fixed in the next patch version and recorded in the CHANGELOG.

## Attack surface of this project

cowork-flow is a CLI with no runtime dependencies. It makes no network requests itself, with one exception: `cwf self update`, which drives npm to query the registry and install the package globally. It collects no telemetry, but it does **write files as you and cause hosts to execute scripts**. Reports worth filing fall into these categories:

| Surface | Related commands | Typical problems |
|---|---|---|
| Writing to the target project | `cwf project init` / `cwf project sync` | Path traversal, writing outside the target directory, or overwriting files it declares as protected (`config.yaml`, `.developer`, `spec/backend/`, `spec/frontend/`, `spec/guides/`, `spec/references/`, `tasks/`, `plans/`) |
| Writing to host configuration directories | `cwf host add` / `cwf host remove` | Writing outside the host directory, breaking the host's own configuration, or deleting entries that do not belong to cowork-flow on uninstall |
| Forwarding to host CLIs | `cwf host add codex`, and so on | Arguments or paths spliced into a host command are executed as extra options |
| Host hooks and injection scripts | Each host's `PostToolUse` hook | Treating tool input (file paths, tool output, task facts) as instructions instead of data |
| Fact layer | `cwf mcp serve` / `./.cowork-flow/run mcp-state` | Exposing project facts to processes that should not see them |
| Skill scripts | `./.cowork-flow/run <command>` | Runtime scripts inside the project triggered into dangerous operations by unexpected input |
| Self-update | `cwf self update` | Pulling an unexpected version from the registry and installing it globally; supply-chain and version-pinning problems |

## Out of scope

- Vulnerabilities in the host products themselves (Codex, Claude Code, OpenCode, ZCode, Qoder, Kimi Code, DeepSeek Harness) — report those to the respective vendors.
- Problems that require an attacker to already be able to execute code on your machine.
- You ran `cwf project sync --force` on a directory you did not want overwritten (the semantics of `--force` are whole-file overwrites of protected files).
- Differences between the version fetched by an unpinned `npx cowork-flow` and the repository's default branch `dev`.
