# cowork-flow

[中文](README.md) | English

An in-repository collaboration workflow for AI coding assistants.

Agree on the goal, the plan, and the scope of changes before work starts, and check
against the project's own rules before calling it done. Task state lives in the
repository, so you can pick the work back up in a new session instead of reconstructing
progress from chat history.

Supports Codex, Claude Code, OpenCode, ZCode, Qoder, Kimi Code, and DeepSeek Harness.

## What it solves

- Keeps requirements, decisions, plans, and the allowed change scope inside the project.
- Makes the assistant read the current task before working, instead of continuing from memory.
- Separates implementation from checking, so a problem sends the work back to implementation.
- Protects custom configuration, project-owned specs, tasks, and plans in an existing project.

cowork-flow is not tied to a tech stack and does not rewrite an existing project with a
scaffold. It only adds a collaboration convention and the files that go with it.

## Where it fits

- You often have an AI handle features or fixes that need several rounds of confirmation.
- You want every task to have an explicit scope, completion conditions, and a check record.
- Work continues across multiple sessions or multiple developers.
- You already use an AI coding host, but task state mostly lives in chat history.

If you only ask questions or change a line or two, or you already have a solid task
system, read up first and decide whether to adopt it.

## Getting started

Node.js 20 or later is required.

### 1. Install the CLI

```bash
npm install -g cowork-flow
cwf --version
```

`cwf` and `cowork-flow` are the same command. To skip the global install, replace `cwf`
below with `npx cowork-flow` — except for `cwf self update`.

### 2. Initialize a project

Preview the files that will be written:

```bash
cwf project init --host codex --developer alice --dry-run
```

Drop `--dry-run` once the list looks right:

```bash
cwf project init --host codex --developer alice --language en-US
```

Without `--language` the default is `zh-CN`; an interactive terminal asks, and a
non-interactive run uses the default. The choice is written to
`.cowork-flow/config.yaml` and affects only task and plan artifacts
(`.cowork-flow/spec/contracts/decision-anchor.md` and
`.cowork-flow/templates/plan-template.md`).

Replace `codex` with the host you use:

`codex`, `claude-code`, `opencode`, `zcode`, `qoder`, `kimi-code`, `dsh`.

The command initializes the current directory by default. For a new project, pass the
target directory as a positional argument, for example
`cwf project init ./my-project --host codex`, then enter that directory. When `--host`
is omitted, init first looks for host markers already in the project (such as
`.codex/` or `.claude/`); an interactive terminal offers a picker when none is found,
and a non-interactive environment needs an explicit host. Use `--host all` only when
the project really will be worked on from several hosts.

Initialization adds `AGENTS.md`, `.cowork-flow/`, and the matching host files. It does
not touch application code. An existing `.developer` is never overwritten; on first
initialization an explicit `--developer` wins over `git config user.name`. With no git
identity, an interactive terminal prompts and a non-interactive run fails (`--dry-run`
only reports `would-skip`). `--platform` / `--platforms` remain accepted aliases of
`--host`. An existing `.cowork-flow/config.yaml` owns its `language`, even under
`--force`; edit that file and run `cwf project sync .` to switch languages. On an
existing project, always run `--dry-run` first.

### 3. Finish host setup

Codex, Claude Code, and OpenCode work in an initialized project as-is. ZCode, Qoder,
DeepSeek Harness, and Kimi Code also need a machine-level component:

```bash
cwf host add <host>
```

See [host integration](docs/hosts.en.md) for each host's exact command, restart
requirements, and special cases.

### 4. Start inside the host

Go back to your AI coding host, open the project root, and start a new session. Describe
what you want, for example:

```text
Use cowork-flow to implement "filter the order list by status". Spell out the
requirements, the plan, and the change scope first, and wait for confirmation before
editing code.
```

To inspect progress by hand, run this in the project root:

```bash
./.cowork-flow/run task next
```

## Day to day

- **Start a new request**: just describe what you want. The assistant confirms the goal, the plan, and the files it may change.
- **Resume a task**: start a new session and say "continue the current task". State and context come from the project, not from the previous chat.
- **Pause a task**: end the session. Task state stays in the project for next time.
- **Update the project**: after upgrading the CLI, preview the sync and then apply it.

```bash
cwf self update
cwf project sync . --dry-run
cwf project sync .
```

`project sync` only updates files cowork-flow manages. Existing configuration,
`spec/backend|frontend|guides|references`, tasks, and plans are kept by default;
framework-managed `spec/contracts|runtime|schemas` and `spec/index.md` follow the
sync. `.cowork-flow/config.yaml` is project configuration and is never overwritten by
`sync --force`. Sync reads its `language` and distributes only that language's
`decision-anchor.md` contract and `.cowork-flow/templates/plan-template.md`; tasks and plans follow that
language by default, and an explicit user request may override it.
**Retired-asset cleanup** deletes obsolete cowork-flow files listed in the
release manifest and touches nothing else. For upgrading machine-level host
components, see [host integration](docs/hosts.en.md).

## Troubleshooting

| Symptom | First move |
|---|---|
| You do not know what to do next | Run `./.cowork-flow/run task next` |
| You worry init or sync will change the wrong files | Add `--dry-run` to the command |
| You want to confirm which hosts the project selected | Run `cwf host list .` |
| Skills, plugins, hooks, or project files look wrong | Run `./.cowork-flow/run doctor --all` |
| You are unsure how to write a command or flag | Run `cwf --help` or `cwf <group> <command> --help` |

For host-specific problems, start with [host integration](docs/hosts.en.md). To understand
how the project is organized, see [architecture and extension](docs/architecture.en.md).

<details>
<summary>Command reference</summary>

| Command | Purpose |
|---|---|
| `cwf project init [target] --host <host> [--developer <name>] [--language zh-CN|en-US] [--dry-run] [--force]` | Initialize a project |
| `cwf project sync [target] [--dry-run] [--force]` | Update the cowork-flow-managed files in a project |
| `cwf host add <host> [--component <name>] [--dry-run] [--force] [--prune-old] [--uninstall]` | Install a machine-level host component |
| `cwf host remove <host> [--component <name>] [--dry-run] [--force]` | Remove a machine-level host component |
| `cwf host list [target] [--json]` | List supported hosts and what the project selected |
| `cwf self update [--dry-run]` | Update the globally installed CLI |
| `cwf dev refresh [target] [--dry-run]` | Refresh the self-instance while maintaining the cowork-flow repo |
| `cwf mcp serve [args...]` | Serve task facts to an MCP client |

Old command names still work; use the new names in new scripts.

| Old name | New name |
|---|---|
| `init` | `cwf project init` |
| `sync` | `cwf project sync` |
| `mcp-state` | `cwf mcp serve` |
| `update` | `cwf self update` |
| `source-refresh` | `cwf dev refresh` |
| `install-zcode-plugin` | `cwf host add zcode` |
| `install-qoder-plugin` | `cwf host add qoder` |
| `install-codex-plugin` | `cwf host add codex` |
| `install-dsh-preset` | `cwf host add dsh --component preset` |
| `install-dsh-hook` | `cwf host add dsh --component hook` |
| `install-kimi-hook` | `cwf host add kimi-code --component hook` |

</details>

## Documentation

The detailed documentation is available in English and Chinese; each page links to its
counterpart at the top.

| Document | Contents |
|---|---|
| [Documentation index](docs/index.en.md) | Entry point for every document |
| [Architecture and extension](docs/architecture.en.md) | How the project files are organized, how the sync policy and protected files work |
| [Host integration](docs/hosts.en.md) | Install, restart, troubleshoot, and uninstall for each host |
| [Release and maintenance](docs/release.en.md) | Tests, CI, and maintainer commands |
| [Direction](docs/direction.en.md) | Positioning, settled trade-offs, version line, and open items |
| [Contributing](CONTRIBUTING.md) | Local setup, commit conventions, and PR checks (Chinese) |
| [Changelog](CHANGELOG.md) | What changed in each version (Chinese) |

## License

[MIT](LICENSE)
