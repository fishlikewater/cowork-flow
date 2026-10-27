# Contributing

[中文](CONTRIBUTING.md) | English

Thanks for contributing to cowork-flow. This document covers only what you need to start work, decide the scope of a change, and open a pull request. For repository structure, see [Architecture and extension](docs/architecture.en.md); for the release process, see [Release and maintenance](docs/release.en.md).

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Node.js | 20 or later | CLI and Node tests |
| Python | 3.10 or later | Template runtime and Python tests |
| Git | Current stable | Task baseline, sync, and host tests |

The repository has no runtime dependencies and no devDependencies. `npm ci` installs no third-party packages; explain the reason and discuss the approach before adding a dependency.

All source code and documentation use UTF-8. The line-ending contract for Windows and POSIX scripts is managed by `.gitattributes`; do not rewrite it by hand.

## Getting started locally

```bash
git clone https://github.com/fishlikewater/cowork-flow.git
cd cowork-flow
npm ci
npm run source:refresh
```

`source:refresh` refreshes this repository's own `.cowork-flow/`, `.agents/skills/`, and `.claude/skills/` from `template/`. Rerun it after changing `template/`; otherwise local tests and `./.cowork-flow/run` keep using the old copies.

This repository also uses cowork-flow. Check the current state before you start changing things:

```bash
./.cowork-flow/run task next --json
```

`AGENTS.md` and `.cowork-flow/spec/` are implementation constraints; do not build a second process beside the current task.

## Decide what to change first

| Change | Main location |
|---|---|
| Files written after project initialization | `template/` |
| Machine-level plugins, presets, and hooks | `presets/` |
| CLI commands and installers | `src/commands/`, `src/lib/` |
| Project runtime | `template/.cowork-flow/scripts/` |
| Host, sync, and skill declarations | `template/.cowork-flow/spec/runtime/host-assets.json` |
| Release, packaging, and test entry scripts | `scripts/` |
| Node tests | `test/` |
| Python tests | `tests/` |
| CI, issue/PR templates, and dependency updates | `.github/` |
| User and maintainer documentation | `README.md`, `README.en.md`, `docs/`, `CONTRIBUTING.md`, `CONTRIBUTING.en.md`, `SECURITY.md`, `SECURITY.en.md` |

When adding or changing behavior, write a test that fails first, then the smallest implementation. Before refactoring, pin the existing behavior so unrelated modules do not change by accident. The root `CONTRIBUTING` and `SECURITY` documents are kept as Chinese/English pairs: change the Chinese source first, then sync the English page.

## Host changes

When integrating or changing a host, usually check all of these:

| Location | Contents |
|---|---|
| `template/.<host>/` | Hooks, agents, commands, and configuration that must be written into the project |
| `template/.cowork-flow/adapters/<host>/adapter.yaml` | Adapter and skill discovery declarations |
| `template/.cowork-flow/spec/runtime/host-assets.json` | Platforms, payloads, sync policy, and migration list |
| `presets/<host>/` | Plugins, presets, or machine-level hooks |
| `src/commands/install-<host>-*.js`, `src/commands/registry.js` | Installation, uninstallation, and command registration |
| `test/host-assets.test.js`, `test/host-command.test.js`, `test/host-inspect.test.js`, `test/<host>-*.test.js`, `tests/test_host_*.py` | Behavior and regression gates |
| `docs/hosts.md`, `docs/hosts.en.md` | Installation prerequisites, upgrades, uninstallation, and troubleshooting |

The table shows where to change things. Host-specific code must not enter the shared layer — see "Extension rules" in [Architecture and extension](docs/architecture.en.md) for the boundary.

## Commit messages

Use Conventional Commits:

```text
<type>(<scope>): <description>
```

Examples:

```text
feat(host): add cwf host inspect
fix(host): correct skill discovery path
refactor(zcode): move the plugin payload to presets/zcode
```

Common types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`. Descriptions may be Chinese or English, matching the repository's existing style; say what changed, not an unverifiable phrase such as "improve the experience".

## Tests and pre-PR checks

Minimum:

```bash
npm run test:fast
git diff --check
```

For which commands to add based on the change scope and what each covers, see "Pre-release checks" in [Release and maintenance](docs/release.en.md) — that is the only list of commands and their applicable scenarios; this document does not repeat it.

`test:fast` runs only the core suites listed in `package.json`. When adding a test file, decide based on the impact whether to add it to that list.

Run `test:fast` for documentation changes too: `test/docs.test.js` validates relative links, each language's index, and the Chinese/English page pairing under `docs/`.

When platform prerequisites are not met, tests may skip explicitly. CI runs its gates on Ubuntu and Windows; a local machine without the prerequisites may skip, but record it honestly — never report a skip as a pass.

A PR description should state:

- What changed and why.
- Which tests ran and their results.
- Which platform cases were skipped or remain unverified.
- Whether installation locations, commands, configuration formats, or upgrade steps changed.

## License

By submitting code you agree to license it under [MIT](LICENSE).
