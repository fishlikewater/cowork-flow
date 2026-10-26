import { join, resolve } from 'node:path';

import { UsageError, extractValueFlag, parseFlags } from '../lib/cli-flags.js';
import { hostRegistry } from '../lib/host-assets.js';
import { pathExists } from '../lib/install-support.js';
import { runInstallCodexPlugin, inspectInstalledState as inspectCodex, FLAGS as CODEX_PLUGIN_FLAGS } from './install-codex-plugin.js';
import { runInstallClaudeCodePlugin, inspectInstalledState as inspectClaude, FLAGS as CLAUDE_CODE_PLUGIN_FLAGS } from './install-claude-code-plugin.js';
import { runInstallDshHook, inspectInstalledState as inspectDshHook, FLAGS as DSH_HOOK_FLAGS } from './install-dsh-hook.js';
import { runInstallDshPreset, inspectInstalledState as inspectDshPreset, FLAGS as DSH_PRESET_FLAGS } from './install-dsh-preset.js';
import { runInstallKimiPlugin, inspectInstalledState as inspectKimiPlugin, FLAGS as KIMI_PLUGIN_FLAGS } from './install-kimi-code-plugin.js';
import { runInstallKimiHook, inspectInstalledState as inspectKimiHook, FLAGS as KIMI_HOOK_FLAGS } from './install-kimi-hook.js';
import { runInstallOpenCodePlugin, inspectInstalledState as inspectOpenCode, FLAGS as OPENCODE_PLUGIN_FLAGS } from './install-opencode-plugin.js';
import { runInstallQoderPlugin, inspectInstalledState as inspectQoder, FLAGS as QODER_PLUGIN_FLAGS } from './install-qoder-plugin.js';
import { runInstallZCodePlugin, inspectInstalledState as inspectZCode, FLAGS as ZCODE_PLUGIN_FLAGS } from './install-zcode-plugin.js';
import { inspectHosts, renderInspectLine } from './host-inspect.js';

const KIMI_ALL_FLAGS = [...new Set([...KIMI_HOOK_FLAGS, ...KIMI_PLUGIN_FLAGS])].sort();


// Which machine-level integrations a host has.
// Deliberately not part of host-assets.json: that manifest
// ships into user projects and declares asset facts, while
// this is a property of the command surface. A gate keeps
// the two in step.
export const HOST_COMPONENTS = {
  codex: {
    default: 'plugin',
    components: {
      plugin: { summary: 'Codex plugin: marketplace source plus the bootstrap skill', flags: CODEX_PLUGIN_FLAGS, run: runInstallCodexPlugin, inspect: inspectCodex }
    }
  },
  'claude-code': {
    default: 'plugin',
    components: {
      plugin: { summary: 'Claude Code skills-directory plugin: the bootstrap skill', flags: CLAUDE_CODE_PLUGIN_FLAGS, run: runInstallClaudeCodePlugin, inspect: inspectClaude }
    }
  },
  opencode: {
    default: 'plugin',
    components: {
      plugin: { summary: 'OpenCode plugin: the plugin file plus the bootstrap skill it registers', flags: OPENCODE_PLUGIN_FLAGS, run: runInstallOpenCodePlugin, inspect: inspectOpenCode }
    }
  },
  zcode: {
    default: 'plugin',
    components: {
      plugin: { summary: 'ZCode plugin: hooks, agents and the bootstrap skill', flags: ZCODE_PLUGIN_FLAGS, run: runInstallZCodePlugin, inspect: inspectZCode }
    }
  },
  qoder: {
    default: 'plugin',
    components: {
      plugin: { summary: 'Qoder plugin: payload, registry entry and enable flag', flags: QODER_PLUGIN_FLAGS, run: runInstallQoderPlugin, inspect: inspectQoder }
    }
  },
  dsh: {
    default: 'preset',
    components: {
      preset: { summary: 'DSH agent preset (bundles the hook, the primary path)', flags: DSH_PRESET_FLAGS, run: runInstallDshPreset, inspect: inspectDshPreset },
      hook: { summary: 'DSH workflow-state hook as a machine-level patch row', flags: DSH_HOOK_FLAGS, run: runInstallDshHook, inspect: inspectDshHook }
    }
  },
  'kimi-code': {
    default: 'all',
    components: {
      plugin: { summary: 'Kimi Code plugin: the bootstrap Skill it loads at session start', flags: KIMI_PLUGIN_FLAGS, run: runInstallKimiPlugin, inspect: inspectKimiPlugin },
      hook: { summary: 'Kimi Code context-injection hook as a user-level config.toml [[hooks]] row', flags: KIMI_HOOK_FLAGS, run: runInstallKimiHook, inspect: inspectKimiHook },
      all: { summary: 'Kimi Code hook plus plugin, installed in one command (the default)', flags: KIMI_ALL_FLAGS, run: runInstallKimiAll }
    }
  }
};


// Every flag any installer accepts, in a stable order.
// `host add` forwards argv unchanged, so installers stay
// the only validators; this list is what `host add --help`
// can name.
export const HOST_FLAGS = [...new Set(
  Object.values(HOST_COMPONENTS).flatMap(
    (host) => Object.values(host.components).flatMap((component) => component.flags)
  )
)].sort();


function withoutForceFlag(args) {
  return args.filter((arg) => arg !== '--force' && !arg.startsWith('--force='));
}


// kimi-code's default component: the hook (injection, the
// required half) first, then the plugin, in one command.
// Both installers stay the only validators — unknown flags
// pass through untouched and are rejected by whichever
// installer reaches them — but `--force` cannot: the hook
// has no such flag, so the combined path strips it for the
// hook segment only, and the plugin still receives it.
async function runInstallKimiAll(args) {
  await runInstallKimiHook(withoutForceFlag(args));
  await runInstallKimiPlugin(args);
}


function resolveHost(token) {
  const id = hostRegistry.platformIdFor(token);
  if (id === null) {
    throw new UsageError(
      `Unknown host: ${token}. Declared hosts: ${hostRegistry.platformIds.join(', ')}`
    );
  }
  const host = HOST_COMPONENTS[id];
  return { id, host };
}


function resolveComponent(id, host, name) {
  const componentName = name ?? host.default;
  const component = host.components[componentName];
  if (!component) {
    throw new UsageError(
      `Host ${id} has no component ${componentName}. `
      + `Components: ${Object.keys(host.components).join(', ')}`
    );
  }
  return component;
}


// `--component` is the only flag these two commands own;
// everything else belongs to the installer and is
// forwarded verbatim, so a flag this module never heard of
// still reaches it and is validated there.
function splitHostArgs(args) {
  const { value: componentName, rest } = extractValueFlag(args, '--component');
  const [token, ...forwarded] = rest;
  if (token === undefined) {
    throw new UsageError('Missing required argument: <host>');
  }
  const { id, host } = resolveHost(token);
  return { id, component: resolveComponent(id, host, componentName), forwarded };
}


export async function runHostAdd(args = []) {
  const { component, forwarded } = splitHostArgs(args);
  return await component.run(forwarded);
}


export async function runHostRemove(args = []) {
  const { component, forwarded } = splitHostArgs(args);
  return await component.run(['--uninstall', ...forwarded]);
}


// Read-only inspection of machine-level installs. The installer for each host
// owns its layout; this command only asks and renders the normalized facts.
export async function runHostInspect(args = [], { io, env = process.env } = {}) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--json'],
    positional: { max: 1, name: '[host]' }
  });
  const hostIds = positionals[0] === undefined
    ? [...hostRegistry.platformIds]
    : [resolveHost(positionals[0]).id];

  const report = await inspectHosts(HOST_COMPONENTS, hostIds, { env });
  if (flags['--json']) {
    io.writeOut(`${JSON.stringify(report, null, 2)}\n`);
    return 0;
  }
  for (const row of report.hosts) {
    io.writeOut(renderInspectLine(row));
  }
  return 0;
}


export async function runHostList(args = [], { io } = {}) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--json'],
    positional: { max: 1, name: '[target]' }
  });
  const target = resolve(positionals[0] ?? process.cwd());

  const rows = [];
  for (const platform of hostRegistry.platforms) {
    // Every declared host has components;
    // cli-registry.test.js asserts it.
    const host = HOST_COMPONENTS[platform.id];
    rows.push({
      id: platform.id,
      displayName: platform.displayName,
      aliases: [...platform.aliases],
      components: Object.keys(host.components),
      defaultComponent: host.default,
      // The per-project adapter record is the selection
      // signal.
      selected: await pathExists(join(target, ...platform.adapterPath.split('/')))
    });
  }

  if (flags['--json']) {
    io.writeOut(`${JSON.stringify({ target, hosts: rows }, null, 2)}\n`);
    return 0;
  }

  const header = ['host', 'name', 'components', 'selected'];
  const table = rows.map((row) => [
    row.id,
    row.displayName,
    row.components.join(', '),
    row.selected ? 'yes' : 'no'
  ]);
  const widths = header.map((cell, index) => Math.max(
    cell.length,
    ...table.map((line) => line[index].length)
  ));
  const format = (line) => line.map((cell, index) => cell.padEnd(widths[index])).join('  ').trimEnd();

  io.writeOut(`Hosts declared in host-assets.json (project: ${target})\n`);
  io.writeOut(`${format(header)}\n`);
  for (const line of table) {
    io.writeOut(`${format(line)}\n`);
  }
  io.writeOut('`selected` means this project has the host\'s adapter.\n');
  return 0;
}
