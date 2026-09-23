import { UsageError } from '../lib/cli-flags.js';
import { hostRegistry } from '../lib/host-assets.js';
import { HOST_COMPONENTS, HOST_FLAGS, runHostAdd, runHostList, runHostRemove } from './host.js';
import { runInit } from './init.js';
import { runMcpState } from './mcp-state.js';
import { runSourceRefresh } from './source-refresh.js';
import { runSync } from './sync.js';
import { runUpdate } from './update.js';


// The command surface, in one place. `src/cli.js` resolves argv against this
// table and dispatches; it holds no command names of its own, and the help text
// is rendered from these same declarations, so a new command cannot appear in
// one and be missing from the other.
export const PROGRAM = 'cwf';

export const GROUPS = [
  { id: 'project', summary: 'Project assets: .cowork-flow/, AGENTS.md, host adapters, skills' },
  { id: 'host', summary: 'Machine-level host integration: plugins, presets, hooks' },
  { id: 'self', summary: 'The installed cowork-flow CLI itself' },
  { id: 'mcp', summary: 'Model Context Protocol integration' },
  { id: 'dev', summary: 'Commands for working on the cowork-flow repository itself' }
];

// Flag descriptions are shared: --dry-run means the same thing everywhere, and
// spelling it out once keeps the help of eight commands from drifting apart.
const FLAG_HELP = {
  '--dry-run': 'Print what would change; write nothing',
  '--force': 'Overwrite an existing installation; on uninstall, also delete the files the managed row alone would leave behind',
  '--prune-old': 'Also delete cached versions other than the current one (zcode only)',
  '--uninstall': 'Remove the integration instead of installing it; same as `cwf host remove <host>`',
  '--json': 'Print machine-readable JSON instead of a table',
  '--component': 'Which machine-level component to act on (dsh has both preset and hook)'
};

const flag = (name) => ({ name, kind: 'boolean', description: FLAG_HELP[name] });
const valueFlag = (name, valueName) => ({ name, kind: 'value', valueName, description: FLAG_HELP[name] });

const PLATFORM_TOKENS = `${hostRegistry.platformIds.join('|')}|all`;
const HOST_NOTE = `Hosts: ${Object.entries(HOST_COMPONENTS)
  .map(([id, host]) => `${id} (${Object.keys(host.components).join(', ')})`)
  .join('; ')}. The other declared hosts have no machine-level component.`;
// The flags are a union across hosts, and the installer that owns the flag is
// what validates it, so the one gap the union creates is named here instead of
// being left for the user to discover as a usage error.
const HOST_FORCE_NOTE = '`--force` applies to every component except kimi-code\'s hook, '
  + 'which overwrites unconditionally and therefore does not accept the flag.';

export const COMMANDS = [
  {
    path: ['project', 'init'],
    summary: 'Copy the cowork-flow template into a project',
    usage: `project init [target] --platform <${PLATFORM_TOKENS}> [--developer <name>] [--dry-run] [--force]`,
    flags: [
      { name: '--platform', kind: 'value', valueName: 'host', repeatable: true, description: 'Host to set the project up for; repeatable and comma-separated' },
      { name: '--platforms', kind: 'value', valueName: 'host', repeatable: true, description: 'Alias of --platform' },
      { name: '--developer', kind: 'value', valueName: 'name', description: 'Developer name recorded in .cowork-flow/.developer' },
      flag('--dry-run'),
      flag('--force')
    ],
    positional: { min: 0, max: 1, name: '[target]' },
    examples: [
      'cwf project init . --platform codex --developer alice',
      'cwf project init ./my-project --platform all --dry-run'
    ],
    run: (args, context) => runInit(args, context)
  },
  {
    path: ['project', 'sync'],
    summary: 'Refresh a project\'s cowork-flow files from the installed template',
    usage: 'project sync [target] [--dry-run] [--force]',
    flags: [flag('--dry-run'), flag('--force')],
    positional: { min: 0, max: 1, name: '[target]' },
    examples: ['cwf project sync ./my-project --dry-run'],
    run: (args, context) => runSync(args, context)
  },
  {
    path: ['host', 'add'],
    summary: 'Install a host\'s machine-level integration',
    usage: 'host add <host> [--component <name>] [--dry-run] [--force] [--prune-old] [--uninstall]',
    // Documentation only: this command forwards its argv to the installer it
    // picks, and the installer is what validates the flags. The list is the
    // union of what the installers declare so the help cannot omit a flag.
    flags: [valueFlag('--component', 'name'), ...HOST_FLAGS.map(flag)],
    notes: [HOST_NOTE, HOST_FORCE_NOTE],
    examples: ['cwf host add codex', 'cwf host add dsh --component hook'],
    run: (args) => runHostAdd(args)
  },
  {
    path: ['host', 'remove'],
    summary: 'Remove a host\'s machine-level integration',
    usage: 'host remove <host> [--component <name>] [--dry-run] [--force]',
    // Documentation only, like `host add`: the flags are forwarded to the
    // installer that owns them. `--force` matters for dsh's hook, where the
    // managed row goes but the plugin file needs the extra flag.
    flags: [valueFlag('--component', 'name'), flag('--dry-run'), flag('--force')],
    notes: [
      HOST_NOTE,
      HOST_FORCE_NOTE,
      'Idempotent: removing something that is not installed reports it and succeeds.',
      'Only cowork-flow\'s own state is removed; other marketplaces, presets and registry entries are left alone.'
    ],
    examples: ['cwf host remove codex', 'cwf host remove dsh --component hook'],
    run: (args) => runHostRemove(args)
  },
  {
    path: ['host', 'list'],
    summary: 'List declared hosts and whether this project selected them',
    usage: 'host list [target] [--json]',
    flags: [flag('--json')],
    positional: { min: 0, max: 1, name: '[target]' },
    notes: ['Reports declarations and project selection only; installed-state health is what `./.cowork-flow/run doctor` checks.'],
    examples: ['cwf host list', 'cwf host list --json'],
    run: (args, context) => runHostList(args, context)
  },
  {
    path: ['self', 'update'],
    summary: 'Update the globally installed cowork-flow package',
    usage: 'self update [--dry-run]',
    flags: [flag('--dry-run')],
    examples: ['cwf self update --dry-run'],
    run: (args, context) => runUpdate(args, context)
  },
  {
    path: ['dev', 'refresh'],
    summary: 'Refresh this checkout\'s self-instance from template/',
    usage: 'dev refresh [target] [--dry-run]',
    flags: [flag('--dry-run')],
    positional: { min: 0, max: 1, name: '[target]' },
    examples: ['cwf dev refresh --dry-run'],
    run: (args, context) => runSourceRefresh(args, context)
  },
  {
    path: ['mcp', 'serve'],
    summary: 'Serve cowork-flow facts over MCP on stdio',
    usage: 'mcp serve [args...]',
    // Everything after the command goes to the project runner unchanged: the
    // runner owns this subcommand's own options, and the npm CLI only resolves
    // the project root and execs it.
    passthrough: true,
    notes: ['Registered once in your MCP client; the project root is resolved by walking up from the client\'s cwd.'],
    run: (args, context) => runMcpState(args, context)
  }
];

// Old names. `permanent` aliases are the spelling users have already written
// outside this repository (MCP client configs) or the short everyday names;
// the rest are shims that print a migration note on stderr and go away after
// two minor releases.
export const ALIASES = [
  { name: 'init', command: ['project', 'init'], args: [], permanent: true },
  { name: 'sync', command: ['project', 'sync'], args: [], permanent: true },
  { name: 'mcp-state', command: ['mcp', 'serve'], args: [], permanent: true },
  { name: 'update', command: ['self', 'update'], args: [], permanent: false },
  { name: 'source-refresh', command: ['dev', 'refresh'], args: [], permanent: false },
  { name: 'install-zcode-plugin', command: ['host', 'add'], args: ['zcode'], permanent: false },
  { name: 'install-qoder-plugin', command: ['host', 'add'], args: ['qoder'], permanent: false },
  { name: 'install-codex-plugin', command: ['host', 'add'], args: ['codex'], permanent: false },
  { name: 'install-dsh-preset', command: ['host', 'add'], args: ['dsh', '--component', 'preset'], permanent: false },
  { name: 'install-dsh-hook', command: ['host', 'add'], args: ['dsh', '--component', 'hook'], permanent: false },
  { name: 'install-kimi-hook', command: ['host', 'add'], args: ['kimi-code'], permanent: false }
];


export function groupFor(token) {
  return GROUPS.find((group) => group.id === token) ?? null;
}


function matchCommand(tokens) {
  let best = null;
  for (const command of COMMANDS) {
    if (command.path.length > tokens.length) {
      continue;
    }
    if (!command.path.every((segment, index) => segment === tokens[index])) {
      continue;
    }
    if (best === null || command.path.length > best.path.length) {
      best = command;
    }
  }
  return best;
}


export function resolve(argv) {
  const alias = ALIASES.find((entry) => entry.name === argv[0]) ?? null;
  const tokens = alias
    ? [...alias.command, ...alias.args, ...argv.slice(1)]
    : [...argv];
  const command = matchCommand(tokens);
  if (command === null) {
    const named = tokens.filter((token) => !token.startsWith('-'));
    throw new UsageError(
      `Unknown command: ${(named.length > 0 ? named : tokens).slice(0, 2).join(' ')}\n`
      + `Run \`${PROGRAM} --help\` to see the available commands.`
    );
  }
  return { command, args: tokens.slice(command.path.length), alias };
}


export function aliasReplacement(alias) {
  return `${PROGRAM} ${[...alias.command, ...alias.args].join(' ')}`;
}


export function aliasNotice(alias) {
  return `note: "${PROGRAM} ${alias.name}" is now "${aliasReplacement(alias)}"; `
    + 'the old name keeps working for two more minor releases.\n';
}


// The help target for an argv that asked for help: aliases are expanded first,
// so asking for help on a legacy name documents where that name now points, and
// anything past the longest matching command is dropped (the trailing
// positionals are not part of a help path).
export function helpPath(argv) {
  const tokens = argv.filter((token) => token !== '--help' && token !== '-h');
  if (tokens[0] === 'help') {
    tokens.shift();
  }
  const alias = ALIASES.find((entry) => entry.name === tokens[0]) ?? null;
  const expanded = alias ? [...alias.command, ...alias.args, ...tokens.slice(1)] : tokens;
  const command = matchCommand(expanded);
  if (command !== null) {
    return [...command.path];
  }
  return groupFor(expanded[0]) ? [expanded[0]] : [];
}


function flagLine(entry) {
  const suffix = entry.kind === 'value' ? ` <${entry.valueName ?? 'value'}>` : '';
  return `  ${entry.name}${suffix}`.padEnd(26) + entry.description;
}


function usageLine(command) {
  return `  ${PROGRAM} ${command.usage}`;
}


function commandBlock(command, { withSummary }) {
  const lines = [usageLine(command)];
  if (withSummary) {
    lines.push(`      ${command.summary}`);
  }
  return lines;
}


function renderRootHelp() {
  const lines = [
    `${PROGRAM} — cowork-flow CLI`,
    '',
    'Usage:',
    `  ${PROGRAM} <group> <command> [options]`,
    `  ${PROGRAM} --help | --version`,
    '',
    'Groups:'
  ];
  const groupWidth = Math.max(...GROUPS.map((group) => group.id.length));
  for (const group of GROUPS) {
    lines.push(`  ${group.id.padEnd(groupWidth)}  ${group.summary}`);
  }
  lines.push('', 'Commands:');
  for (const command of COMMANDS) {
    lines.push(...commandBlock(command, { withSummary: true }));
  }
  lines.push(
    '',
    'Global options:',
    '  -h, --help'.padEnd(26) + 'Show help for a group or a command',
    '  -v, --version'.padEnd(26) + 'Print the installed version',
    '',
    'Old command names (all still work):'
  );
  const aliasWidth = Math.max(...ALIASES.map((alias) => alias.name.length));
  for (const alias of ALIASES) {
    const suffix = alias.permanent ? '(permanent)' : '(removed after two minor releases)';
    lines.push(`  ${alias.name.padEnd(aliasWidth)}  -> ${aliasReplacement(alias)}  ${suffix}`);
  }
  return `${lines.join('\n')}\n`;
}


function renderGroupHelp(group) {
  const commands = COMMANDS.filter((command) => command.path[0] === group.id);
  const lines = [
    `${PROGRAM} ${group.id} — ${group.summary}`,
    '',
    'Usage:',
    `  ${PROGRAM} ${group.id} <command> [options]`,
    '',
    'Commands:'
  ];
  for (const command of commands) {
    lines.push(...commandBlock(command, { withSummary: true }));
  }
  return `${lines.join('\n')}\n`;
}


function renderCommandHelp(command) {
  const lines = [
    `${PROGRAM} ${command.path.join(' ')} — ${command.summary}`,
    '',
    'Usage:',
    usageLine(command)
  ];
  if (command.passthrough) {
    lines.push('', 'Arguments are passed through to the project runner unchanged.');
  } else if (command.flags?.length > 0) {
    lines.push('', 'Options:');
    for (const entry of command.flags) {
      lines.push(flagLine(entry));
    }
  }
  if (command.notes?.length > 0) {
    lines.push('');
    for (const note of command.notes) {
      lines.push(note);
    }
  }
  if (command.examples?.length > 0) {
    lines.push('', 'Examples:');
    for (const example of command.examples) {
      lines.push(`  ${example}`);
    }
  }
  return `${lines.join('\n')}\n`;
}


export function renderHelp(path = []) {
  const group = groupFor(path[0]);
  if (!group) {
    return renderRootHelp();
  }
  if (path.length === 1) {
    return renderGroupHelp(group);
  }
  const command = COMMANDS.find((entry) => entry.path.join(' ') === path.join(' '));
  return command ? renderCommandHelp(command) : renderGroupHelp(group);
}
