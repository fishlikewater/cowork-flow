import { access } from 'node:fs/promises';
import { join, resolve } from 'node:path';

import { UsageError, extractValueFlag, parseFlags } from '../lib/cli-flags.js';
import { hostRegistry } from '../lib/host-assets.js';
import { runInstallCodexPlugin, FLAGS as CODEX_PLUGIN_FLAGS } from './install-codex-plugin.js';
import { runInstallClaudeCodePlugin, FLAGS as CLAUDE_CODE_PLUGIN_FLAGS } from './install-claude-code-plugin.js';
import { runInstallDshHook, FLAGS as DSH_HOOK_FLAGS } from './install-dsh-hook.js';
import { runInstallDshPreset, FLAGS as DSH_PRESET_FLAGS } from './install-dsh-preset.js';
import { runInstallKimiPlugin, FLAGS as KIMI_PLUGIN_FLAGS } from './install-kimi-code-plugin.js';
import { runInstallKimiHook, FLAGS as KIMI_HOOK_FLAGS } from './install-kimi-hook.js';
import { runInstallOpenCodePlugin, FLAGS as OPENCODE_PLUGIN_FLAGS } from './install-opencode-plugin.js';
import { runInstallQoderPlugin, FLAGS as QODER_PLUGIN_FLAGS } from './install-qoder-plugin.js';
import { runInstallZCodePlugin, FLAGS as ZCODE_PLUGIN_FLAGS } from './install-zcode-plugin.js';


// Which machine-level integrations a host has. This is deliberately not part of
// host-assets.json: that manifest ships into user projects and declares host
// facts (asset paths, skill discovery, where the payload lives in the package),
// while "which actions can the CLI take against this host" is a property of the
// command surface. The two are kept in step by a gate instead (see
// test/cli-registry.test.js), not by merging the files. Every declared host has
// an entry here — a gate asserts it.
export const HOST_COMPONENTS = {
  codex: {
    default: 'plugin',
    components: {
      plugin: { summary: 'Codex plugin: marketplace source plus the bootstrap skill', flags: CODEX_PLUGIN_FLAGS, run: runInstallCodexPlugin }
    }
  },
  'claude-code': {
    default: 'plugin',
    components: {
      plugin: { summary: 'Claude Code skills-directory plugin: the bootstrap skill', flags: CLAUDE_CODE_PLUGIN_FLAGS, run: runInstallClaudeCodePlugin }
    }
  },
  opencode: {
    default: 'plugin',
    components: {
      plugin: { summary: 'OpenCode plugin: the plugin file plus the bootstrap skill it registers', flags: OPENCODE_PLUGIN_FLAGS, run: runInstallOpenCodePlugin }
    }
  },
  zcode: {
    default: 'plugin',
    components: {
      plugin: { summary: 'ZCode plugin: hooks, agents and the bootstrap skill', flags: ZCODE_PLUGIN_FLAGS, run: runInstallZCodePlugin }
    }
  },
  qoder: {
    default: 'plugin',
    components: {
      plugin: { summary: 'Qoder plugin: payload, registry entry and enable flag', flags: QODER_PLUGIN_FLAGS, run: runInstallQoderPlugin }
    }
  },
  dsh: {
    default: 'preset',
    components: {
      preset: { summary: 'DSH agent preset (bundles the hook, the primary path)', flags: DSH_PRESET_FLAGS, run: runInstallDshPreset },
      hook: { summary: 'DSH workflow-state hook as a machine-level patch row', flags: DSH_HOOK_FLAGS, run: runInstallDshHook }
    }
  },
  'kimi-code': {
    default: 'plugin',
    components: {
      plugin: { summary: 'Kimi Code plugin: the bootstrap Skill it loads at session start', flags: KIMI_PLUGIN_FLAGS, run: runInstallKimiPlugin },
      hook: { summary: 'Kimi Code context-injection hook (fallback when no plugin is installed)', flags: KIMI_HOOK_FLAGS, run: runInstallKimiHook }
    }
  }
};


// Every flag any installer accepts, in a stable order. `host add` forwards its
// argv to the installer unchanged, so the installer stays the only place that
// validates a flag; this list exists so `host add --help` can name them.
export const HOST_FLAGS = [...new Set(
  Object.values(HOST_COMPONENTS).flatMap(
    (host) => Object.values(host.components).flatMap((component) => component.flags)
  )
)].sort();


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


async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


// `--component` is the only flag `host add`/`host remove` own; everything else
// belongs to the installer and is forwarded verbatim, so a flag this module has
// never heard of still reaches the installer and is validated there.
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


export async function runHostList(args = [], { io } = {}) {
  const { flags, positionals } = parseFlags(args, {
    boolean: ['--json'],
    positional: { max: 1, name: '[target]' }
  });
  const target = resolve(positionals[0] ?? process.cwd());

  const rows = [];
  for (const platform of hostRegistry.platforms) {
    // Every declared host has components; test/cli-registry.test.js asserts it.
    const host = HOST_COMPONENTS[platform.id];
    rows.push({
      id: platform.id,
      displayName: platform.displayName,
      aliases: [...platform.aliases],
      components: Object.keys(host.components),
      defaultComponent: host.default,
      // The adapter declaration is the per-project record that this host was
      // selected at init, so its presence is the selection signal.
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
