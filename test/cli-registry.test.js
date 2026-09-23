import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { test } from 'node:test';

import {
  ALIASES,
  COMMANDS,
  GROUPS,
  aliasReplacement,
  groupFor,
  helpPath,
  renderHelp,
  resolve
} from '../src/commands/registry.js';
import { HOST_COMPONENTS, HOST_FLAGS } from '../src/commands/host.js';
import { loadHostAssetManifest } from '../src/lib/host-assets.js';
import { packageRoot } from '../src/lib/paths.js';

const manifest = loadHostAssetManifest();

function commandFor(path) {
  return COMMANDS.find((command) => command.path.join(' ') === path.join(' '));
}

test('every declared command resolves to itself with no arguments left over', () => {
  for (const command of COMMANDS) {
    const { command: resolved, args, alias } = resolve([...command.path]);
    assert.equal(resolved, command);
    assert.deepEqual(args, []);
    assert.equal(alias, null);
  }
});

test('every command path starts at a declared group', () => {
  for (const command of COMMANDS) {
    assert.ok(
      groupFor(command.path[0]),
      `${command.path.join(' ')} does not start at a declared group`
    );
  }
});

test('every group has at least one command', () => {
  for (const group of GROUPS) {
    assert.ok(
      COMMANDS.some((command) => command.path[0] === group.id),
      `group ${group.id} has no command`
    );
  }
});

test('every alias resolves to its target and keeps the trailing arguments', () => {
  for (const alias of ALIASES) {
    const target = commandFor(alias.command);
    assert.ok(target, `alias ${alias.name} points at undeclared command ${alias.command.join(' ')}`);

    const { command, args, alias: matched } = resolve([alias.name, '--dry-run', 'extra']);
    assert.equal(command, target);
    assert.equal(matched, alias);
    assert.deepEqual(args, [...alias.args, '--dry-run', 'extra']);
  }
});

// The roadmap fixes the split: three names users have already written outside
// this repository stay forever, the rest are shims that go away.
test('the permanent aliases are exactly the ones users already wrote down', () => {
  const permanent = ALIASES.filter((alias) => alias.permanent).map((alias) => alias.name).sort();
  assert.deepEqual(permanent, ['init', 'mcp-state', 'sync']);
  assert.equal(ALIASES.length, 11);
});

test('the root help renders every command from the registry', () => {
  const help = renderHelp([]);
  for (const command of COMMANDS) {
    assert.ok(help.includes(`cwf ${command.usage}`), `root help omits ${command.path.join(' ')}`);
  }
  for (const group of GROUPS) {
    assert.ok(help.includes(`${group.id}`), `root help omits group ${group.id}`);
  }
  for (const alias of ALIASES) {
    assert.ok(help.includes(aliasReplacement(alias)), `root help omits where ${alias.name} points`);
  }
});

test('each group help renders only that group, and each command help its own flags', () => {
  for (const group of GROUPS) {
    const help = renderHelp([group.id]);
    for (const command of COMMANDS.filter((entry) => entry.path[0] === group.id)) {
      assert.ok(help.includes(`cwf ${command.usage}`), `${group.id} help omits ${command.path.join(' ')}`);
    }
    for (const command of COMMANDS.filter((entry) => entry.path[0] !== group.id)) {
      assert.ok(!help.includes(`cwf ${command.usage}`), `${group.id} help leaks ${command.path.join(' ')}`);
    }
  }

  for (const command of COMMANDS) {
    const help = renderHelp(command.path);
    assert.ok(help.includes(command.summary));
    for (const entry of command.flags ?? []) {
      assert.ok(help.includes(entry.name), `${command.path.join(' ')} help omits ${entry.name}`);
      assert.ok(help.includes(entry.description), `${command.path.join(' ')} help omits ${entry.name} description`);
    }
  }
});

test('help paths resolve through aliases and stop at the longest command', () => {
  assert.deepEqual(helpPath(['--help']), []);
  assert.deepEqual(helpPath(['host', '--help']), ['host']);
  assert.deepEqual(helpPath(['host', 'add', 'codex', '--help']), ['host', 'add']);
  assert.deepEqual(helpPath(['help', 'host', 'add']), ['host', 'add']);
  assert.deepEqual(helpPath(['install-dsh-hook', '--help']), ['host', 'add']);
  // An unknown command asking for help gets the root help, not an error.
  assert.deepEqual(helpPath(['nonsense', '--help']), []);
});

// The command surface and the host manifest are separate files on purpose, so
// the link between them has to be asserted rather than assumed.
test('the machine-level component table only names declared hosts', () => {
  for (const id of Object.keys(HOST_COMPONENTS)) {
    assert.ok(
      manifest.platforms.some((platform) => platform.id === id),
      `HOST_COMPONENTS names ${id}, which host-assets.json does not declare`
    );
  }
});

test('a host has a plugin component exactly when it declares a plugin payload', () => {
  const withPayload = manifest.platforms
    .filter((platform) => platform.payload !== null)
    .map((platform) => platform.id)
    .sort();
  const withPluginComponent = Object.entries(HOST_COMPONENTS)
    .filter(([, host]) => Object.hasOwn(host.components, 'plugin'))
    .map(([id]) => id)
    .sort();

  assert.deepEqual(withPluginComponent, withPayload);
});

test('the default component of every host is one of its components', () => {
  for (const [id, host] of Object.entries(HOST_COMPONENTS)) {
    assert.ok(
      Object.hasOwn(host.components, host.default),
      `${id} defaults to ${host.default}, which is not one of its components`
    );
    for (const component of Object.values(host.components)) {
      assert.equal(typeof component.run, 'function', `${id} has a component without a runner`);
      assert.ok(Array.isArray(component.flags), `${id} has a component without a flag list`);
    }
  }
});

// `host add` forwards argv to whichever installer it picks, so its help is the
// union of what those installers accept. A flag added to an installer but not
// reaching this list would be documented nowhere.
test('host add documents every flag its installers accept', () => {
  const declared = new Set(
    (commandFor(['host', 'add']).flags ?? []).map((entry) => entry.name)
  );
  assert.deepEqual([...declared].sort(), ['--component', ...HOST_FLAGS].sort());

  for (const [id, host] of Object.entries(HOST_COMPONENTS)) {
    for (const [name, component] of Object.entries(host.components)) {
      for (const flag of component.flags) {
        assert.ok(declared.has(flag), `${id}/${name} accepts ${flag}, which host add does not document`);
      }
    }
  }
});

test('host remove documents the component selector, dry-run and force', () => {
  const declared = (commandFor(['host', 'remove']).flags ?? []).map((entry) => entry.name).sort();
  assert.deepEqual(declared, ['--component', '--dry-run', '--force']);
});

// Every installer reached through `host add` has to be reachable through
// `host remove` too: an install path without an uninstall path is a machine
// that can only accumulate state.
test('every installer accepts --uninstall', () => {
  for (const [id, host] of Object.entries(HOST_COMPONENTS)) {
    for (const [name, component] of Object.entries(host.components)) {
      assert.ok(
        component.flags.includes('--uninstall'),
        `${id}/${name} cannot be uninstalled through host remove`
      );
    }
  }
});

// The migration is only finished when nothing points at the retired spelling
// any more: a hint that tells a user to run a shim keeps the shim alive forever.
//
// Two strings are wire format rather than guidance. The managed-block markers
// are already written into user machine files and are how an existing install
// is recognised for idempotent replacement — changing them would make every
// installed block unrecognisable and append a second one — so they keep naming
// the old commands on purpose, and the marker copies in the tests must stay
// byte-identical to them.
const WIRE_FORMAT_MARKERS = [
  '# cowork-flow: managed workflow-state-hook row. Run "cowork-flow install-dsh-hook" to change it.',
  '# cowork-flow: kimi hook start. Managed by "cowork-flow install-kimi-hook"; edits inside this block are replaced.'
];

const SCANNED_ROOTS = ['src', 'template', 'presets', 'tests', 'test', 'docs'];
const SCANNED_EXTENSIONS = new Set(['.js', '.mjs', '.py', '.md', '.json', '.yaml', '.yml', '.toml']);
// Config formats carry guidance in comments too (a YAML comment naming the
// command), so they join markdown in the bare-name pass. JSON does not: it has
// no comments, so a bare name there would be data or a path, not a hint.
const COMMENTED_EXTENSIONS = ['.md', '.yaml', '.yml', '.toml'];
// CHANGELOG.md is excluded on purpose: past entries are history and are not
// rewritten. README.md is excluded too, because its alias table is the
// documented home of the old names; it is covered instead by the derived
// assertion below, which fails if the README stops documenting a command or an
// alias the registry declares.
const SHIM_NAMES = ALIASES.filter((alias) => !alias.permanent).map((alias) => alias.name);
// Documentation also writes the command without its executable prefix ("run
// install-kimi-hook"), so commented surfaces get a second pass on the bare
// name. Only names that cannot be ordinary prose take part: `update` and `sync`
// are English words, and a bare-name pass for them would match every sentence
// that mentions updating a file.
const BARE_NAME_SHIMS = SHIM_NAMES.filter((name) => name !== 'update' && name !== 'sync');

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '__pycache__') {
        continue;
      }
      yield* walk(path);
    } else if (SCANNED_EXTENSIONS.has(entry.name.slice(entry.name.lastIndexOf('.')))) {
      yield path;
    }
  }
}

test('no shipped hint still points at a retired command name', async () => {
  const offenders = [];

  for (const root of SCANNED_ROOTS) {
    for await (const path of walk(join(packageRoot, ...root.split('/')))) {
      const relativePath = relative(packageRoot, path).split('\\').join('/');
      let text = await readFile(path, 'utf8');
      for (const marker of WIRE_FORMAT_MARKERS) {
        text = text.split(marker).join('');
      }
      for (const name of SHIM_NAMES) {
        // With the executable prefix, the name is unambiguously a command.
        const invoked = new RegExp('(?:cwf|cowork-flow)\\s+' + name + '(?![\\w-])');
        if (invoked.test(text)) {
          offenders.push(`${relativePath}: ${name}`);
        }
      }
      if (COMMENTED_EXTENSIONS.some((extension) => relativePath.endsWith(extension))) {
        for (const name of BARE_NAME_SHIMS) {
          // Two guards, both about paths rather than prose: a token sitting
          // inside a path (`src/commands/install-kimi-hook.js`) names the
          // module, not the command, so a leading `/` or `.` excludes it, and a
          // trailing `.js` does the same. A trailing full stop is a sentence
          // ending, not an extension, so only a dot followed by a word
          // character counts as one.
          const bare = new RegExp('(^|[^\\w/.-])' + name + '(?![\\w-])(?!\\.\\w)');
          if (bare.test(text)) {
            offenders.push(`${relativePath}: ${name} (bare)`);
          }
        }
      }
    }
  }

  assert.deepEqual(offenders, []);
});

// The exemption above only works while the markers still say what it thinks
// they say; if one is edited, the gate must stop exempting it.
test('the wire-format markers are still installed verbatim', async () => {
  const sources = [
    ['src/commands/install-dsh-hook.js', WIRE_FORMAT_MARKERS[0]],
    ['src/commands/install-kimi-hook.js', WIRE_FORMAT_MARKERS[1]]
  ];
  for (const [relativePath, marker] of sources) {
    const text = await readFile(join(packageRoot, ...relativePath.split('/')), 'utf8');
    assert.ok(text.includes(marker), `${relativePath} no longer carries its managed-block marker verbatim`);
  }

  const pin = await readFile(join(packageRoot, 'test', 'dsh-home-patch.test.js'), 'utf8');
  assert.ok(
    pin.includes(WIRE_FORMAT_MARKERS[0]),
    'test/dsh-home-patch.test.js must pin the same marker the installer writes'
  );
});

// README is the user-facing command guide and is deliberately outside the
// residue scan (its alias table is where the old names belong), so it gets its
// own derived assertion: a command or alias that exists in the registry and not
// in the README is exactly the drift the registry exists to prevent.
test('README documents every command and every alias from the registry', async () => {
  const readme = await readFile(join(packageRoot, 'README.md'), 'utf8');

  for (const command of COMMANDS) {
    // The command table row, not just a prose mention: a command that appears
    // only in passing is not documented.
    assert.ok(
      readme.includes(`| \`cwf ${command.path.join(' ')}`),
      `README has no command-table row for cwf ${command.path.join(' ')}`
    );
  }
  for (const alias of ALIASES) {
    assert.ok(
      readme.includes(`| \`${alias.name}\` | \`${aliasReplacement(alias)}\``),
      `README does not map ${alias.name} to ${aliasReplacement(alias)}`
    );
  }
  for (const group of GROUPS) {
    assert.ok(readme.includes(group.id), `README never mentions the ${group.id} group`);
  }
});

test('the scanned roots exist', async () => {
  for (const root of SCANNED_ROOTS) {
    const entries = await readdir(join(packageRoot, ...root.split('/')));
    assert.ok(entries.length > 0, `${root} is empty, so the residue gate scans nothing there`);
  }
});
