import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { runInstallCodexPlugin } from '../src/commands/install-codex-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot, templateRoot } from '../src/lib/paths.js';
import { readPluginMetadata } from '../src/lib/plugin-metadata.js';

const HOSTS = ['zcode', 'qoder', 'codex'];
const BOOTSTRAP_SKILL = 'cowork-flow-bootstrap';
const MARKETPLACE_NAME = 'cowork-flow-local';
const PLUGIN_KEY = 'cowork-flow@cowork-flow-local';
const ENV_KEYS = ['CODEX_HOME', 'COWORK_FLOW_CODEX', 'CODEX_STUB_STATE', 'CODEX_STUB_LOG'];

// The stub speaks the subset of `codex plugin` the installer uses, and persists
// registration in a state file so install-then-list behaves like the real CLI.
const STUB_SOURCE = `const { appendFileSync, readFileSync, writeFileSync } = require('node:fs');
const { join } = require('node:path');

const args = process.argv.slice(2);
const statePath = process.env.CODEX_STUB_STATE;
const read = () => {
  try {
    return JSON.parse(readFileSync(statePath, 'utf8'));
  } catch {
    return {};
  }
};
const write = (state) => writeFileSync(statePath, JSON.stringify(state, null, 2) + '\\n');
appendFileSync(process.env.CODEX_STUB_LOG, args.join(' ') + '\\n');
const state = read();
const marketplaceVersion = () => {
  try {
    const manifest = join(state.marketplace.root, 'plugins', 'cowork-flow', '.codex-plugin', 'plugin.json');
    return JSON.parse(readFileSync(manifest, 'utf8')).version;
  } catch {
    return null;
  }
};

if (args[1] === 'marketplace' && args[2] === 'add') {
  state.marketplace = { name: 'cowork-flow-local', root: args[3] };
  write(state);
  console.log('Added marketplace \`cowork-flow-local\` from ' + args[3] + '.');
  process.exit(0);
}
if (args[1] === 'marketplace' && args[2] === 'list') {
  console.log(JSON.stringify({ marketplaces: state.marketplace ? [state.marketplace] : [] }));
  process.exit(0);
}
if (args[1] === 'marketplace' && args[2] === 'remove') {
  if (!state.marketplace || state.marketplace.name !== args[3]) {
    console.error('Error: marketplace \`' + args[3] + '\` is not configured or installed');
    process.exit(1);
  }
  delete state.marketplace;
  write(state);
  console.log('Removed marketplace \`' + args[3] + '\`.');
  process.exit(0);
}
if (args[1] === 'add') {
  const version = marketplaceVersion();
  const [name, marketplaceName] = args[2].split('@');
  state.plugin = { pluginId: args[2], name, marketplaceName, version, installed: true, enabled: true };
  write(state);
  console.log(JSON.stringify({
    pluginId: args[2],
    name,
    marketplaceName,
    version,
    installedPath: join(state.marketplace.root, 'plugins', name, version)
  }));
  process.exit(0);
}
if (args[1] === 'list') {
  console.log(JSON.stringify({ installed: state.plugin ? [state.plugin] : [], available: [] }));
  process.exit(0);
}
if (args[1] === 'remove') {
  delete state.plugin;
  write(state);
  console.log('Removed plugin \`' + args[2] + '\`.');
  process.exit(0);
}
console.error('stub: unsupported invocation ' + args.join(' '));
process.exit(2);
`;

function hostPluginRoot(host) {
  return join(packageRoot, 'presets', host);
}

function marketplaceRoot(codexHome) {
  return join(codexHome, 'plugins', 'marketplaces', MARKETPLACE_NAME);
}

function pluginTarget(codexHome) {
  return join(marketplaceRoot(codexHome), 'plugins', 'cowork-flow');
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function pathExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function readLog(path) {
  try {
    return (await readFile(path, 'utf8')).split('\n').filter(Boolean);
  } catch {
    return [];
  }
}

// The installer also queries state (`marketplace list` / `plugin list`); these
// tests assert on what it changes.
function mutations(lines) {
  return lines.filter((line) => line.includes(' add ') || line.includes(' remove '));
}

async function captureConsole(fn) {
  const lines = [];
  const original = console.log;
  console.log = (...args) => {
    lines.push(args.join(' '));
  };
  try {
    await fn();
  } finally {
    console.log = original;
  }
  return lines.join('\n');
}

// A shebang launcher only execs on POSIX, so Windows gets a .cmd shim; the
// installer spawns .cmd/.bat through a shell, which is the same path npm takes.
async function createCodexStub(t, { spaced = false } = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-codex-stub-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  // Windows shell mode concatenates the command with spaces and escapes
  // nothing, so a CLI under a spaced path is where a missing quote shows up.
  const launcherDir = spaced ? join(dir, 'spaced stub') : dir;
  await mkdir(launcherDir, { recursive: true });

  const script = join(launcherDir, 'codex-stub.js');
  await writeFile(script, STUB_SOURCE, 'utf8');
  if (process.platform === 'win32') {
    const launcher = join(launcherDir, 'codex.cmd');
    await writeFile(launcher, `@echo off\r\n"${process.execPath}" "${script}" %*\r\n`, 'utf8');
    return launcher;
  }
  const launcher = join(launcherDir, 'codex');
  await writeFile(launcher, `#!/bin/sh\nexec "${process.execPath}" "${script}" "$@"\n`, {
    mode: 0o755
  });
  return launcher;
}

function useEnv(t, overrides) {
  const previous = new Map(ENV_KEYS.map((key) => [key, process.env[key]]));
  t.after(() => {
    for (const [key, value] of previous) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  });
  for (const [key, value] of Object.entries(overrides)) {
    process.env[key] = value;
  }
}

async function createCodexHome(t, options = {}) {
  const base = await mkdtemp(join(tmpdir(), 'cowork-flow-codex-home-'));
  t.after(async () => {
    await rm(base, { recursive: true, force: true });
  });
  // A spaced home also puts a space into the marketplace root the installer
  // hands to the CLI, which is the argument Windows shell mode would split.
  const home = options.spaced ? join(base, 'spaced home') : base;
  await mkdir(home, { recursive: true });
  const state = join(home, 'stub-state.json');
  const log = join(home, 'stub-log.txt');
  const overrides = { CODEX_HOME: home, CODEX_STUB_STATE: state, CODEX_STUB_LOG: log };
  if (options.cli === false) {
    overrides.COWORK_FLOW_CODEX = join(home, 'missing-codex');
  } else {
    overrides.COWORK_FLOW_CODEX = await createCodexStub(t, { spaced: options.spaced === true });
  }
  useEnv(t, overrides);
  return { home, state, log };
}

test('codex plugin payload carries the bootstrap Skill and no agents', async () => {
  const pluginRoot = hostPluginRoot('codex');
  const manifest = await readJson(join(pluginRoot, '.codex-plugin', 'plugin.json'));

  assert.equal(manifest.name, 'cowork-flow');
  assert.equal(manifest.skills, './skills/');
  await access(join(pluginRoot, 'skills', BOOTSTRAP_SKILL, 'SKILL.md'));

  // Codex loads skills/hooks/mcp/apps from a plugin root but never agents: a
  // malformed agents/*.toml is reported at the project level and silently
  // ignored from a plugin (probe task 09-23-codex-plugin-probe). The three fixed
  // subagents stay project-level, so the payload must not grow an agents/
  // directory that codex would drop on the floor.
  assert.equal(manifest.agents, undefined);
  assert.equal(manifest.hooks, undefined);
  await assert.rejects(access(join(pluginRoot, 'agents')));
});

test('bootstrap Skill payload is byte-identical across hosts', async () => {
  const contents = await Promise.all(
    HOSTS.map((host) =>
      readFile(join(hostPluginRoot(host), 'skills', BOOTSTRAP_SKILL, 'SKILL.md'), 'utf8')
    )
  );

  for (const [index, content] of contents.entries()) {
    assert.equal(content, contents[0], `${HOSTS[index]} payload must match the shared bootstrap Skill`);
  }
});

test('payload Skill names stay disjoint from project Skills', async () => {
  for (const host of HOSTS) {
    const skillsRoot = join(hostPluginRoot(host), 'skills');
    const names = await readdir(skillsRoot);

    assert.ok(names.includes(BOOTSTRAP_SKILL), `${host} payload must ship the bootstrap Skill`);
    for (const name of names) {
      await assert.rejects(
        access(join(templateRoot, 'skills', name)),
        `${host} payload Skill ${name} must not shadow a project Skill`
      );
    }
  }
});

test('install-codex-plugin materializes the marketplace and delegates registration', async (t) => {
  const { home, state, log } = await createCodexHome(t);
  const { version } = await readPackageInfo();

  await runInstallCodexPlugin([]);

  const root = marketplaceRoot(home);
  const metadata = await readPluginMetadata();
  const manifest = await readJson(join(root, '.agents', 'plugins', 'marketplace.json'));
  assert.equal(manifest.name, MARKETPLACE_NAME);
  assert.equal(manifest.interface.displayName, `${metadata.displayName} (local)`);
  // codex validates every entry: an explicit install/auth policy and a category.
  assert.deepEqual(manifest.plugins, [
    {
      name: 'cowork-flow',
      source: { source: 'local', path: './plugins/cowork-flow' },
      policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
      category: metadata.category
    }
  ]);

  // The payload is stamped with the release version: an installed payload must
  // agree with the version codex records for it.
  const installedManifest = await readJson(join(pluginTarget(home), '.codex-plugin', 'plugin.json'));
  assert.equal(installedManifest.version, version);
  await access(join(pluginTarget(home), 'skills', BOOTSTRAP_SKILL, 'SKILL.md'));
  await assert.rejects(access(join(pluginTarget(home), 'agents')));
  // codex resolves interface.logo against the plugin root, so the mark has to
  // survive the copy into $CODEX_HOME — a manifest naming a file the payload
  // does not carry renders as a broken image with no error anywhere.
  await access(
    join(pluginTarget(home), ...installedManifest.interface.logo.replace('./', '').split('/'))
  );

  assert.deepEqual(mutations(await readLog(log)), [
    `plugin marketplace add ${root}`,
    `plugin add ${PLUGIN_KEY} --json`
  ]);
  const recorded = await readJson(state);
  assert.equal(recorded.plugin.pluginId, PLUGIN_KEY);
  assert.equal(recorded.plugin.version, version);
  assert.equal(recorded.plugin.enabled, true);
});

test('install-codex-plugin skips a redundant registration when the version matches', async (t) => {
  const { log } = await createCodexHome(t);

  await runInstallCodexPlugin([]);
  await writeFile(log, '', 'utf8');

  const output = await captureConsole(() => runInstallCodexPlugin([]));

  assert.match(output, /already installed/);
  assert.deepEqual(mutations(await readLog(log)), [], 'a matching version must not re-register');
});

test('install-codex-plugin re-registers after a version change', async (t) => {
  const { home, state, log } = await createCodexHome(t);
  const { version } = await readPackageInfo();
  await writeFile(
    state,
    JSON.stringify(
      {
        marketplace: { name: MARKETPLACE_NAME, root: marketplaceRoot(home) },
        plugin: {
          pluginId: PLUGIN_KEY,
          name: 'cowork-flow',
          marketplaceName: MARKETPLACE_NAME,
          version: '0.0.1',
          installed: true,
          enabled: true
        }
      },
      null,
      2
    ),
    'utf8'
  );

  await runInstallCodexPlugin([]);

  assert.deepEqual(mutations(await readLog(log)), [`plugin add ${PLUGIN_KEY} --json`]);
  assert.equal((await readJson(state)).plugin.version, version);
});

test('install-codex-plugin treats an equivalent marketplace root spelling as the same registration', async (t) => {
  const { home, state, log } = await createCodexHome(t);
  await runInstallCodexPlugin([]);

  // Codex records its own canonical spelling of the source root, and on Windows
  // that is neither case-stable nor free of the \\?\ extended-length prefix; the
  // same directory must not read as a second, conflicting registration.
  const recorded = await readJson(state);
  recorded.marketplace.root = process.platform === 'win32'
    ? `\\\\?\\${recorded.marketplace.root.toUpperCase()}`
    : `${recorded.marketplace.root}/`;
  await writeFile(state, JSON.stringify(recorded, null, 2) + '\n', 'utf8');
  await writeFile(log, '', 'utf8');

  const output = await captureConsole(() => runInstallCodexPlugin([]));

  assert.doesNotMatch(output, /remove it first/);
  assert.match(output, /already installed/);
  assert.deepEqual(mutations(await readLog(log)), [], 'an equivalent root must not re-register');
});

test('install-codex-plugin refuses a marketplace registered from another root', async (t) => {
  const { home, state } = await createCodexHome(t);
  await writeFile(
    state,
    JSON.stringify(
      { marketplace: { name: MARKETPLACE_NAME, root: join(home, 'elsewhere') } },
      null,
      2
    ),
    'utf8'
  );

  let code;
  const output = await captureConsole(async () => {
    code = await runInstallCodexPlugin([]);
  });

  assert.match(output, /remove it first: codex plugin marketplace remove cowork-flow-local/);
  assert.equal(code, 1, 'installing over a foreign registration must fail closed');
});

test('install-codex-plugin dry-run writes nothing', async (t) => {
  const { home, log } = await createCodexHome(t);

  const output = await captureConsole(() => runInstallCodexPlugin(['--dry-run']));

  assert.match(output, new RegExp(`codex plugin add ${PLUGIN_KEY}`));
  assert.equal(await pathExists(marketplaceRoot(home)), false);
  assert.deepEqual(await readLog(log), []);
});

test('install-codex-plugin uninstall removes registration and payload', async (t) => {
  const { home, state, log } = await createCodexHome(t);

  await runInstallCodexPlugin([]);
  await writeFile(log, '', 'utf8');
  await runInstallCodexPlugin(['--uninstall']);

  assert.deepEqual(mutations(await readLog(log)), [
    `plugin remove ${PLUGIN_KEY}`,
    `plugin marketplace remove ${MARKETPLACE_NAME}`
  ]);
  assert.equal(await pathExists(marketplaceRoot(home)), false);
  const recorded = await readJson(state);
  assert.equal(recorded.plugin, undefined);
  assert.equal(recorded.marketplace, undefined);
});

test('install-codex-plugin leaves manual commands when no codex CLI is available', async (t) => {
  const { home, log } = await createCodexHome(t, { cli: false });

  const output = await captureConsole(() => runInstallCodexPlugin([]));

  // The marketplace source is still prepared, so the printed commands are the
  // only step left for the user.
  assert.equal(await pathExists(join(marketplaceRoot(home), '.agents', 'plugins', 'marketplace.json')), true);
  assert.match(output, new RegExp(`codex plugin marketplace add .*${MARKETPLACE_NAME}`));
  assert.match(output, new RegExp(`codex plugin add ${PLUGIN_KEY}`));
  assert.deepEqual(await readLog(log), []);
});

test('install-codex-plugin survives a codex CLI and marketplace root containing spaces', async (t) => {
  const { home, log } = await createCodexHome(t, { spaced: true });
  const root = marketplaceRoot(home);
  assert.ok(root.includes(' '), 'the case must actually exercise a spaced path');

  await runInstallCodexPlugin([]);

  // Windows spawns a .cmd CLI through a shell, which splits unquoted tokens:
  // the registration must still reach the CLI with the full root.
  assert.deepEqual(mutations(await readLog(log)), [
    `plugin marketplace add ${root}`,
    `plugin add ${PLUGIN_KEY} --json`
  ]);
  assert.equal(await pathExists(join(pluginTarget(home), 'skills', BOOTSTRAP_SKILL, 'SKILL.md')), true);
});

test('install-codex-plugin uninstall without a CLI prints the unregister commands', async (t) => {
  const { home, log } = await createCodexHome(t, { cli: false });

  const output = await captureConsole(() => runInstallCodexPlugin(['--uninstall']));

  // The source directory is gone after an uninstall, so repeating the install
  // commands here would send the user the wrong way.
  assert.doesNotMatch(output, /register it with/);
  assert.match(output, new RegExp(`codex plugin remove ${PLUGIN_KEY}`));
  assert.match(output, new RegExp(`codex plugin marketplace remove ${MARKETPLACE_NAME}`));
  assert.equal(await pathExists(marketplaceRoot(home)), false);
  assert.deepEqual(await readLog(log), []);
});
