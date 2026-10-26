# Architecture and extension

[中文](architecture.md) | English

This document is for developers maintaining cowork-flow. It explains how the project files are layered, where host differences live, and which boundaries to respect when adding capabilities. If you only want to install and use cowork-flow, see [README](../README.en.md); to troubleshoot a specific host, see [Host integration](hosts.en.md).

## Three boundaries to remember first

1. `template/` only holds files that get written into a user project.
2. `presets/` only holds machine-level payloads that `cwf host add` installs into host configuration directories.
3. Host differences are declared by `template/.cowork-flow/spec/runtime/host-assets.json` and are not written into the shared runtime.

## Repository responsibilities

| Location | Responsibility |
|---|---|
| `template/` | The single distribution source for `project init` and `project sync` |
| `presets/` | Payload source for plugins, presets, and machine-level hooks |
| `src/` | Node CLI: command registration, installers, and file sync plans |
| `scripts/` | Build, test, packaging, and release scripts |
| `test/` | Node tests and helper modules |
| `tests/` | Python repository tests and fixtures |
| `docs/` | User, host, architecture, and maintenance documentation |
| `.agents/`, `.claude/`, `.codex/`, `.cowork-flow/` | Runtime copies for this source repository; not a distribution source |

### Project distribution source

The content in `template/` that directly relates to a user project includes:

- `AGENTS.md`: the project collaboration entry point.
- `template/skills/`: the single source for project Skills, distributed per host by `init` / `sync`.
- `template/.cowork-flow/`: project configuration, the Python runtime, specs, plans, and tasks.
- `template/.<host>/`: host configuration, hooks, or agents that must be stored with the project.

`cwf project init` / `cwf project sync` must not read content from the source repository's runtime copies.

### Machine-level payloads

`presets/` stores host components that do not belong to a single project:

- Codex, Claude Code, OpenCode, ZCode, Qoder, and Kimi Code plugins.
- DeepSeek Harness presets and hooks.
- Plugin branding assets and bootstrap Skills.

Machine-level installers may write into host configuration directories only through `cwf host add` / `cwf host remove`, and must not hard-code user home directory paths into `template/`.

Reading machine-level install state has one path too: each installer exports `inspectInstalledState` describing the layout it writes, `cwf host inspect` normalizes those facts into read-only `schemaVersion: 1` rows, and the doctor consumes only that model. The Python runtime does not parse host registries, TOML, settings, or payload manifests; when the read is unavailable the doctor reports `HOST-INSPECT-UNAVAILABLE` instead of mistaking "could not read" for "not installed". See `spec/contracts/host-install-inspection.md`.

## Runtime layers

Runtime code lives in `template/.cowork-flow/scripts/`. The repository root `scripts/` only handles building and releasing.

| Layer | Location | Responsibility |
|---|---|---|
| Command adapters | `scripts/adapters/cli/` | Argument parsing, command output, and CLI exit codes |
| Task services | `scripts/services/` | Task creation, lifecycle, archiving, context, and the task tree |
| State storage | `scripts/infra/storage/` | UTF-8 reads and writes, revision checks, operation logs, and recoverable transactions |
| Host adapters | `scripts/adapters/host/` | Host input, policy differences, and state injection |
| Shared hook core | `scripts/adapters/host/workflow_state_hook.py` | Workflow state parsing shared by all hosts |
| Host declarations | `spec/runtime/host-assets.json` | Platforms, assets, sync policy, Skill roots, and the migration manifest |

The workflow kernel keeps a narrow responsibility: the kernel only resolves state facts and actions, Skill ownership is injected by the manifest loader, and hard gates are enforced by the runtime gate. The repository no longer maintains a second workflow hub or a separate Skill registration control plane.

Scripts needed by an individual Skill live in `template/skills/<skill-id>/scripts/` and do not enter the runtime kernel.

## init and sync

Installers and the synchronizer do not read and write incrementally; they execute in the following order:

1. Read the Host Asset Manifest and the sync policy.
2. Build an immutable Asset Plan.
3. Stage on the same file system, and verify file hashes and permissions.
4. Commit according to the backup manifest; on failure, roll back in reverse order.
5. Update `.cowork-flow/.version` last.

`config.yaml`, `.developer`, specs, tasks, and plans are protected by the sync policy. `--force` widens the overwrite range, but `.cowork-flow/config.yaml` is in `forceProtectedFiles`: once created, neither `init --force` nor `sync --force` overwrites it. For an existing project, run with `--dry-run` first to see the changes.

The installation language is written to `language` in `config.yaml` (`zh-CN` by default, or `en-US`). The `localization` field of the Host Asset Manifest declares which assets have language variants; their source files live under `template/locales/<language>/<canonical-path>`. `init`, `sync`, and `dev refresh` choose the source file through `localizedSource()`, while the target path is always the canonical path, and `locales/` is excluded by `excludedPrefixes` so it never enters the project. Currently only `spec/contracts/decision-anchor.md` and `.cowork-flow/templates/plan-template.md` are localized: the former sets the heading language of a new anchor, the latter sets the language of plan artifacts, and parsers always accept both Chinese and English headings. The start gate for strict non-Tiny tasks additionally requires the plan and anchor to use the configured-language template shape and a filled `Spec check:` / `规范核对：` result; the template placeholder blocks start, while Tiny and legacy tasks are unaffected.

`.cowork-flow/spec/` splits its sync policy by ownership. Framework-maintained `spec/contracts/`, `spec/runtime/`, `spec/schemas/`, and `spec/index.md` follow `sync`: contract errata, `contract-registry.json`, `host-assets.json`, `scope-rules.json`, and schemas therefore reach installed projects in the same generation as the scripts, and obsolete framework spec files registered in `obsoleteFiles` are deleted as well. Project-maintained `spec/backend/`, `spec/frontend/`, `spec/guides/`, and `spec/references/` stay protected, and a normal `sync` never overwrites or deletes files there. The cost is that a project which has locally modified a framework contract or `scope-rules.json` loses those changes on the next `sync`; customizations worth keeping should go into the four project directories, `AGENTS.md`, `config.yaml`, or a project-owned Skill.

## Extension rules

- Host specializations may live only in `spec/runtime/host-assets.json`, `scripts/adapters/`, `template/.<host>/`, or an explicit host command module.
- Plugins provide only fields the host actually supports; do not copy unknown or invalid keys.
- Project Skills are distributed only from `template/skills/`; machine-level payloads do not copy a project Skill with the same name.
- Shared planning and copy modules in `scripts/services|runtime|infra` and `src/lib/` must not contain host branches.
- For a new host, update the Host Asset Manifest and schema first, then add the installer, doctor support, and tests; do not write a separate host list in several files.
- Write project differences into `AGENTS.md`, `config.yaml`, `spec/backend|frontend|guides|references`, or a project-owned Skill, and do not bring back a second set of workflow documents.
- When changing a Skill distribution path, update `skillReadRoot`, `skillDiscovery`, and the corresponding host evidence together.
- When changing a command name, update the command registry, README, doctor hints, Skills, and related tests in one pass.

## Tests and bytecode

Tests and Skill scripts must not leave `__pycache__` or `*.pyc` under `template/` or `presets/`. Node tests redirect the cache through `test/helpers/bytecode-isolation.js`; Skill scripts disable bytecode writing through `runtime_pythonpath_env(cache_bytecode=False)`. `tests/test_no_legacy_template_paths.py` guards this boundary.

`node --test` loads every `.js` file under `test/`, so helper modules must also be free of side effects; on the Python side, tests are collected according to the default discovery rules of pytest or unittest.
