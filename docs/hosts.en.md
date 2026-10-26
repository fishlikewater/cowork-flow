# Host integration

[中文](hosts.md) | English

This document explains how to connect cowork-flow to an AI coding host, and how to check, upgrade, and uninstall it after installation. If you only need the first-time install, start with "Finish host setup" in the [README](../README.en.md).

## Two kinds of files to tell apart first

| Kind | Written to | Installed by |
|---|---|---|
| Project-level files | the current project's `AGENTS.md`, `.cowork-flow/`, and host directories | `cwf project init` / `cwf project sync` |
| Machine-level components | the host's user configuration directory, such as plugins, presets, or hooks | `cwf host add` / `cwf host remove` |

Every project needs at least one `cwf project init`. When `--host` is omitted, init first detects host markers already in the project (such as `.codex/` or `.claude/`), using the same detection as `cwf project sync`; an interactive terminal offers a picker when none is found, while a non-interactive environment must pass `--host` explicitly. `--platform` / `--platforms` remain accepted aliases. Task and plan artifacts default to Chinese; pass `--language en-US` when a non-interactive install needs English artifacts, or edit `language` in `.cowork-flow/config.yaml` and run `cwf project sync` to switch after installation.

Whether `cwf host add` is needed depends on the host:

| Host | Machine-level component needed after init | Suggested command |
|---|---|---|
| Codex | Works in the current project as-is; the global bootstrap entry point is optional | `cwf host add codex` |
| Claude Code | Works in the current project as-is; the global bootstrap entry point is optional | `cwf host add claude-code` |
| OpenCode | Works in the current project as-is; the global bootstrap entry point is optional | `cwf host add opencode` |
| ZCode | Required | `cwf host add zcode` |
| Qoder | Required | `cwf host add qoder` |
| DeepSeek Harness | Required | `cwf host add dsh` |
| Kimi Code | Required | `cwf host add kimi-code` (one command installs both the hook and the plugin) |

## Common commands

Preview first, then install:

```bash
cwf host add <host> --dry-run
cwf host add <host>
```

List the hosts the project and the CLI know about:

```bash
cwf host list .
cwf host list . --json
```

Upgrade or reinstall:

```bash
cwf host add <host> --force
```

Uninstall the machine-level component:

```bash
cwf host remove <host>
```

Use `--force` only once you have confirmed that an existing installation needs to be overwritten. The installer refuses by default to overwrite or delete files it does not own; `--dry-run` runs the same ownership checks.

Machine-level hooks and the project runtime upgrade independently, yet a machine-level hook fires in any workspace — including projects whose runtime is older than the hook. The four machine-level injection shims (Qoder, ZCode, Kimi Code, OpenCode) are therefore **fail-open**: when the project runtime fails, they only record the reason in the host's run log and return 0; they do not inject, and they never turn "hook failed" into "your input is rejected". The project-level Edit-time hooks (Claude Code / Codex) have likewise stopped returning a non-zero exit since 2.0.0 and are always advisory. In an old project, injection silently has no effect; run `cwf project sync .` once to restore it.

## Install-state inspection

`cwf host list` only answers "which hosts are declared and which did the project select"; to see what is actually installed on the machine, use the read-only `cwf host inspect`:

```bash
cwf host inspect
cwf host inspect qoder
cwf host inspect --json
```

One row per installable component, with status `installed`, `missing`, `stale`, `broken`, or `unsupported`. `stale` means the installed payload version differs from the running CLI version; `broken` means the host knows about cowork-flow but a required payload artifact is absent. The doctor then compares that same version with the project's `.cowork-flow/.version`: a CLI newer than the project with a payload that still matches the project's runtime stays silent, while a payload that lags a synced project is still `PLUGIN-STALE`. `kimi-code`'s `all` is only a command composition and never appears as a row. The command is read-only and never repairs, installs, or uninstalls; an unhealthy install is data, not a command failure, and only usage errors such as an unknown host exit with 2.

The doctor's host checks consume the same read model (`cwf host inspect --json`) and no longer parse host directories, registries, settings, or TOML themselves. When the CLI is not on `PATH`, exits non-zero, times out, or reports an unexpected `schemaVersion`, the doctor emits `HOST-INSPECT-UNAVAILABLE` with an upgrade hint instead of falsely reporting `PLUGIN-NOT-INSTALLED` — "could not read" and "read as not installed" are different facts. See `spec/contracts/host-install-inspection.md` for the full contract.

## Codex

```bash
cwf host add codex --dry-run
cwf host add codex
cwf host remove codex
```

The installer will:

- Prepare a stable plugin source under `$CODEX_HOME/plugins/marketplaces/cowork-flow-local/`; when `CODEX_HOME` is unset, it uses `~/.codex`.
- Register the marketplace and the plugin through Codex's official CLI; it does not hand-write `config.toml`.
- When the `codex` command is not found, still prepare the source directory and print the manual commands.

The plugin only carries the `cowork-flow-bootstrap` bootstrap Skill; project hooks and the three fixed subagents are still provided by project-level files. Start a new session after installing or upgrading.

To upgrade to a new version, run:

```bash
cwf host add codex --force
```

## Claude Code

```bash
cwf host add claude-code --dry-run
cwf host add claude-code
cwf host remove claude-code
```

The plugin is written to `$CLAUDE_CONFIG_DIR/skills/cowork-flow`, or `~/.claude/skills/cowork-flow` when that variable is unset. Claude Code treats a Skill directory containing `.claude-plugin/plugin.json` as a plugin, so no extra marketplace command is needed.

The plugin only provides the bootstrap Skill. Project hooks and agents already live in `.claude/`, which avoids duplicate execution from multiple hook sources. Start a new session after installing.

`~/.claude/skills/` is user-maintained: when the target directory is not the cowork-flow plugin, both install and uninstall refuse; use `--force` only after deciding to take over that directory.

## OpenCode

```bash
cwf host add opencode --dry-run
cwf host add opencode
cwf host remove opencode
```

The install location is `$XDG_CONFIG_HOME/opencode/`, or `~/.config/opencode` when that variable is unset. The installer only writes `plugins/cowork-flow.js` and `cowork-flow/`; it does not modify the user's `opencode.json`.

The plugin registers the `cowork-flow-bootstrap` Skill directory shipped in its payload from the `config` hook, so a repository that has not initialized cowork-flow also sees the bootstrap entry point. Start a new session after installing.

The plugin itself is only a transport shim: the injected text is rendered by the in-project Python runtime `inject.py --host opencode` (zcode has the same shape). The payload also carries a cached copy of `cowork-flow/runtime/scripts` to render the not-initialized context outside a project; inside a project, the project's own runtime copy always wins.

OpenCode may generate `package.json`, `bun.lock`, and `node_modules/` inside the plugin directory. These are host files; the installer neither modifies nor cleans them. The load order of multiple plugins, and the precedence between a global and a project Skill of the same name, have not been measured yet.

## ZCode

```bash
cwf host add zcode --dry-run
cwf host add zcode
cwf host add zcode --force --prune-old
cwf host remove zcode
```

The installer maintains a stable marketplace source and the currently active copy; the plugin cache lives under `~/.zcode/cli/plugins/cache/`. The plugin provides hooks, the three fixed subagents, and the bootstrap Skill; project Skills are still provided by `.agents/skills/`.

Old version caches are kept by default, so a running session does not suddenly lose the plugin. Use `--prune-old` when you need to clean up old versions. Restart ZCode or start a new session after upgrading.

## Qoder

```bash
cwf host add qoder --dry-run
cwf host add qoder
cwf host add qoder --force
cwf host remove qoder
```

The install location is determined by `QODER_CONFIG_DIR`, or `~/.qoder` when that variable is unset. The plugin provides hooks, the three fixed subagents, and the bootstrap Skill; the project-level `init` / `sync` commands only write the adaptation declarations and shared Skills.

## DeepSeek Harness

Installs the Cowork Flow preset by default:

```bash
cwf host add dsh --component preset --dry-run
cwf host add dsh
cwf host remove dsh --component preset
```

The preset writes both delivery lines at once, because the desktop version switched channels:

| Location | Applies to | How to enable |
| --- | --- | --- |
| `~/.dsh/.agent-presets/cowork-flow/` (or the corresponding directory under `$DSH_HOME`) | DSH 0.1.x / CLI line | Appears directly in the session's preset list; restart and select **Cowork Flow** |
| `~/.dsh/bundles/cowork-flow/` | DSH 0.2.0+ (desktop) | On the desktop sidebar's Plugins page, enter the absolute path of that directory to install it (the `plugin_manager` tool row is disabled in the desktop host composition and is unavailable in a session), then start a new session |

As of 0.2.0 the host no longer reads the `.agent-presets/` directory (its bundled Skill text reads: "Nothing reads that directory any more"), and the preset becomes one declaration line for `@deepseek-ai/dsh-agent-preset` in a bundle patch. The host performs the bundle installation — it runs the package install and writes the profile manifest — so `cwf` only produces the bundle and the installation instructions, and does not rewrite `~/.dsh/profiles/**`. The two lines differ only in the two places where the host API differs: the workflow line (0.1.x `dsh-workflow-worker-thread` / 0.2.0 `dsh-workflow-ptc`) and the persona line's configuration key (0.1.x `text` / 0.2.0 `prefix`), substituted when the bundle is generated; both must match the target line, because a package that cannot be resolved or a configuration key the host rejects makes the host treat the **entire** preset as unavailable. An install without `--force` only adds the missing line and does not overwrite an existing directory.

The preset already includes the workflow-state hook, so the hook component does not need to be installed as well. Use it only when debugging the composition layer's configuration:

```bash
cwf host add dsh --component hook
cwf host remove dsh --component hook
```

Whether the hook line enters the agent prompt depends on the version line: in testing, DSH 0.1.1-rc.1 did not collect host-layer sections, so live injection could only come from the preset; 0.2.0-rc.1 (desktop) composes the global-layer sections into every agent prompt (`dsh-scope`'s `layers.merge()` takes the global layer first, and the scope chain then overrides it), so on that version the hook component alone can provide injection. The above is code- and documentation-level evidence; real-session verification still requires one run on the corresponding version.

## Kimi Code

The bare command installs both parts in one go: first the context-injection hook (required), then the plugin:

```bash
cwf host add kimi-code
cwf host remove kimi-code
```

Reload the configuration or start a new session after installing or updating. The hook component always rewrites its own hook block and does not write the plugin; the plugin component provides the global bootstrap Skill in uninitialized projects. To install just one half, use `--component`:

```bash
cwf host add kimi-code --component plugin
cwf host add kimi-code --component hook
```

The hook component does not accept `--force` (it always takes over and rewrites its own block); `--force` on the bare command applies only to the plugin part:

```bash
cwf host add kimi-code --force
```

The plugin is materialized to `$KIMI_CODE_HOME/plugins/sources/cowork-flow/` (the stable reinstall source) and `$KIMI_CODE_HOME/plugins/managed/cowork-flow/` (the copy the host loads), and writes directly into the host's plugin registry `$KIMI_CODE_HOME/plugins/installed.json`, matching Kimi Code's own on-disk installation format. Restarting Kimi Code is enough to take effect; no manual install in the TUI is needed. Uninstall cleans up both directories and the registry entry in reverse.

## MCP client integration

When an MCP client needs to read task facts, registering once globally is recommended:

```bash
cwf mcp serve
```

The client searches upward from the current working directory for `.cowork-flow/`, so one registration can serve multiple projects. Common configuration examples:

```toml
# Codex: ~/.codex/config.toml
[mcp_servers.cowork-flow]
command = "cwf"
args = ["mcp", "serve"]
```

```json
// OpenCode: ~/.config/opencode/opencode.json
{
  "mcp": {
    "cowork-flow": {
      "type": "local",
      "command": ["cwf", "mcp", "serve"],
      "enabled": true
    }
  }
}
```

For Claude Code, run:

```bash
claude mcp add -s user cowork-flow -- cwf mcp serve
```

Without a global CLI install, you can also configure the in-project entry point directly:

```bash
<project>/.cowork-flow/run mcp-state
```

## Skill discovery

The single source for project Skills is `template/skills/`; `init` / `sync` distributes them as shown in the table below. Host plugins no longer carry copies of project Skills.

| Host | Project Skill read root | Host discovery |
|---|---|---|
| Codex | `.agents/skills/` | Natively scans `.agents/skills/` |
| Claude Code | `.claude/skills/` | Natively scans the project's `.claude/skills/` |
| OpenCode | `.agents/skills/` | Scans `.agents/skills/` and `.opencode/skills/`; cowork-flow only delivers the former |
| ZCode | `.agents/skills/` | Scans the project's `.zcode/skills/` and `.agents/skills/`; the former wins on a name collision |
| Qoder | `.agents/skills/` | `loadFromAgentsDirectory` is enabled by default |
| Kimi Code | `.agents/skills/` | `PROJECT_GENERIC_DIRS` includes `.agents/skills` |
| DeepSeek Harness | `.agents/skills/` | `skill-filesystem` uses it as the project Skill root |

These channels are recorded as `verified:` in the Host Asset Manifest. After a host upgrade, if you observe behavior changes, update the evidence and tests rather than only the documentation.

## Diagnostics

Start with:

```bash
./.cowork-flow/run doctor --all
./.cowork-flow/run doctor --all --json
```

<details>
<summary>Common diagnostic codes</summary>

| Scope | Diagnostic code | Meaning |
|---|---|---|
| General Skills | `SKILL-READROOT-MISSING` | The project is missing a declared Skill read root |
| General Skills | `PLUGIN-SKILLS-LEGACY` | An old plugin still carries copies of project Skills; reinstall the plugin |
| General Skills | `SKILL-DISCOVERY-GATED` | The host needs the directory trusted or a restart before it loads Skills |
| Codex | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-DISABLED` | The plugin is not registered, its payload is missing, or it is not enabled |
| Claude Code / OpenCode | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-STALE` | The plugin is not installed, its payload is incomplete, or its version is behind |
| Qoder | `PLUGIN-NOT-INSTALLED` / `PLUGIN-PAYLOAD-MISSING` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-DISABLED` / `PLUGIN-STALE` | Something is wrong with the plugin's installation, enablement, payload, or version |
| DSH preset | `PRESET-UNKNOWN-VERSION` / `PRESET-STALE` | The preset lacks a version marker or its version is behind |
| DSH / Kimi hook | `HOOK-NOT-INSTALLED` / `HOOK-SHIM-MISSING` / `HOOK-UNKNOWN-VERSION` / `HOOK-STALE` | The hook block, script, version marker, or version does not match |
| Kimi plugin | `PLUGIN-NOT-INSTALLED` / `PLUGIN-DISABLED` / `PLUGIN-PAYLOAD-INCOMPLETE` / `PLUGIN-STALE` / `PLUGIN-SOURCES-MISSING` | The plugin is not registered, is disabled, has an incomplete payload, is behind, or its source directory is missing |

`PLUGIN-NOT-INSTALLED` means the registry has no cowork-flow record yet; `cwf host add kimi-code` both installs and registers it in one step.

</details>

## Plugin icon fields

Hosts support different manifest fields, so do not copy the same set of fields into every manifest.

| Host | Supported fields | Requirement |
|---|---|---|
| Codex | `interface.logo`, `interface.brandColor` | The logo must be a relative path inside the payload |
| ZCode | the marketplace entry's `icon` | Must be an `https://` URL |
| Claude Code, OpenCode, Qoder, DSH, Kimi Code | None | Do not write icon keys |

`assets/icon.svg` is the single source for the brand icon, and `presets/plugin-meta.json` stores the brand color. Run `npm run icons:export` at release time to re-export the raster assets.

## Environment variables

| Variable | Purpose |
|---|---|
| `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1` | Disable hook injection for all hosts |
| `COWORK_FLOW_CONTEXT_ID` | Explicitly set the session identity; use when the host provides no session variable |
| `COWORK_FLOW_HOST` | Explicitly set the host id |
| `COWORK_FLOW_CODEX` | Set the Codex CLI executable |
| `COWORK_FLOW_CLI` | Set the cowork-flow CLI the doctor uses to read install state; a `.js`, `.mjs` or `.cjs` path runs through node |
| `DSH_HOME` | Override the DeepSeek Harness configuration root |
| `KIMI_CODE_HOME` | Override the Kimi Code configuration root |
| `CODEX_HOME` | Override the Codex configuration root |
| `QODER_CONFIG_DIR` | Override the Qoder configuration root |
| `CLAUDE_CONFIG_DIR` | Override the Claude Code configuration root |
| `COWORK_FLOW_BROWSER` | Browser executable used by `icons:export` |
