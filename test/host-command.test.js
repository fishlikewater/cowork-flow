import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { HOST_COMPONENTS, runHostAdd, runHostInspect, runHostList, runHostRemove } from '../src/commands/host.js';
import { loadHostAssetManifest } from '../src/lib/host-assets.js';
import { installedRegistryPath } from '../src/lib/kimi-installed-registry.js';

const HOME_KEYS = [
  'CLAUDE_CONFIG_DIR',
  'CODEX_HOME',
  'COWORK_FLOW_CODEX',
  'DSH_HOME',
  'KIMI_CODE_HOME',
  'QODER_CONFIG_DIR',
  'XDG_CONFIG_HOME',
  'ZCODE_HOME'
];

function useEnv(t, overrides) {
  const previous = new Map(HOME_KEYS.map((key) => [key, process.env[key]]));
  t.after(() => {
    for (const [key, value] of previous) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  });
  for (const key of HOME_KEYS) {
    delete process.env[key];
  }
  Object.assign(process.env, overrides);
}

async function createTempDir(t, prefix) {
  const dir = await mkdtemp(join(tmpdir(), prefix));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}

// Every host installer prints with console.log, so the command wrappers have to
// be observed the same way.
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

function createIo() {
  return {
    stdout: '',
    stderr: '',
    writeOut(message) {
      this.stdout += message;
    },
    writeErr(message) {
      this.stderr += message;
    }
  };
}

// The three artifacts a kimi-code hook install leaves behind, plus the plugin
// registry the plugin segment writes.
function kimiConfig(home) {
  return join(home, 'config.toml');
}

function kimiShim(home) {
  return join(home, 'hooks', 'cowork-flow-inject.mjs');
}

function kimiMarker(home) {
  return join(home, 'hooks', '.cowork-flow-kimi-hook.json');
}

async function exists(path) {
  try {
    await readFile(path);
    return true;
  } catch {
    return false;
  }
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function createKimiHome(t) {
  const home = await createTempDir(t, 'cowork-flow-host-kimi-all-');
  useEnv(t, { KIMI_CODE_HOME: home });
  return home;
}

test('host add sends each host to its own installer', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-add-');
  useEnv(t, {
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    XDG_CONFIG_HOME: join(home, 'xdg'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    QODER_CONFIG_DIR: join(home, 'qoder'),
    ZCODE_HOME: join(home, 'zcode')
  });

  const cases = [
    { argv: ['opencode'], expect: /OpenCode plugin/ },
    { argv: ['claude-code'], expect: /Claude Code plugin/ },
    { argv: ['codex'], expect: /Codex plugin/ },
    { argv: ['zcode'], expect: /ZCode plugin/ },
    { argv: ['qoder'], expect: /Qoder plugin/ },
    { argv: ['kimi-code'], expect: /Kimi Code plugin/ },
  ];
  for (const { argv, expect } of cases) {
    const output = await captureConsole(() => runHostAdd([...argv, '--dry-run']));
    assert.match(output, expect, `host add ${argv.join(' ')} did not reach its installer`);
  }
});

// dsh lists two components, so it is where a default that silently picked the
// wrong one would show up.
test('host add picks the dsh component from --component and defaults to the preset', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-dsh-');
  useEnv(t, { DSH_HOME: home });

  const byDefault = await captureConsole(() => runHostAdd(['dsh', '--dry-run']));
  const explicitPreset = await captureConsole(() => runHostAdd(['dsh', '--component', 'preset', '--dry-run']));
  const hook = await captureConsole(() => runHostAdd(['dsh', '--component', 'hook', '--dry-run']));

  assert.match(byDefault, /Would install DSH preset/);
  assert.equal(byDefault, explicitPreset);
  assert.match(hook, /Would install workflow-state hook/);
  assert.doesNotMatch(hook, /DSH preset/);
});

test('host add accepts a host alias and the --component=<value> form', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-alias-');
  useEnv(t, { DSH_HOME: home });

  const alias = await captureConsole(() => runHostAdd(['dsh', '--component=hook', '--dry-run']));
  assert.match(alias, /Would install workflow-state hook/);

  const kimiAlias = await captureConsole(() => runHostAdd(['kimi', '--dry-run']));
  assert.match(kimiAlias, /Kimi Code plugin/);
});

test('host remove reaches the uninstall path of every component', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-remove-');
  useEnv(t, {
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    XDG_CONFIG_HOME: join(home, 'xdg'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    QODER_CONFIG_DIR: join(home, 'qoder'),
    ZCODE_HOME: join(home, 'zcode')
  });

  const cases = [
    { argv: ['opencode'], expect: /cowork-flow OpenCode plugin was not installed/ },
    { argv: ['claude-code'], expect: /cowork-flow Claude Code plugin was not installed/ },
    { argv: ['codex'], expect: /Would run: codex plugin remove/ },
    { argv: ['zcode'], expect: /Would remove cowork-flow ZCode plugin/ },
    { argv: ['qoder'], expect: /Would remove cowork-flow@cowork-flow-local/ },
    { argv: ['kimi-code'], expect: /cowork-flow Kimi Code plugin was not installed/ },
    { argv: ['dsh', '--component', 'preset'], expect: /Would uninstall DSH preset/ },
    { argv: ['dsh', '--component', 'hook'], expect: /Would uninstall workflow-state hook/ }
  ];
  for (const { argv, expect } of cases) {
    const output = await captureConsole(() => runHostRemove([...argv, '--dry-run']));
    assert.match(output, expect, `host remove ${argv.join(' ')} did not reach an uninstall path`);
  }
});

// `--uninstall` is documented as equivalent to `host remove`, so the two
// spellings have to be the same code path and not two implementations.
test('host add --uninstall is the same path as host remove', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-uninstall-flag-');
  useEnv(t, { QODER_CONFIG_DIR: join(home, 'qoder') });

  const viaRemove = await captureConsole(() => runHostRemove(['qoder', '--dry-run']));
  const viaFlag = await captureConsole(() => runHostAdd(['qoder', '--uninstall', '--dry-run']));

  assert.equal(viaFlag, viaRemove);
});

test('host list --json reports every declared host and this project selection', async (t) => {
  const target = await createTempDir(t, 'cowork-flow-host-list-');
  const io = createIo();

  const code = await runHostList(['--json', target], { io });
  assert.equal(code, 0);

  const report = JSON.parse(io.stdout);
  const manifest = loadHostAssetManifest();
  assert.equal(report.target, target);
  assert.deepEqual(
    report.hosts.map((host) => host.id),
    manifest.platforms.map((platform) => platform.id)
  );

  for (const host of report.hosts) {
    assert.deepEqual(host.components, Object.keys(HOST_COMPONENTS[host.id]?.components ?? {}));
    assert.equal(host.defaultComponent, HOST_COMPONENTS[host.id]?.default ?? null);
    assert.equal(host.selected, false, `${host.id} cannot be selected in an empty project`);
  }
});

test('host list reads the selection from the target project adapters', async (t) => {
  const target = await createTempDir(t, 'cowork-flow-host-selected-');
  await mkdir(join(target, '.cowork-flow', 'adapters', 'codex'), { recursive: true });
  await writeFile(
    join(target, '.cowork-flow', 'adapters', 'codex', 'adapter.yaml'),
    'id: codex\n',
    'utf8'
  );
  const io = createIo();

  await runHostList(['--json', target], { io });
  const report = JSON.parse(io.stdout);
  const selected = report.hosts.filter((host) => host.selected).map((host) => host.id);

  assert.deepEqual(selected, ['codex']);
});

test('host list prints a table of every host and its components', async (t) => {
  const target = await createTempDir(t, 'cowork-flow-host-table-');
  const io = createIo();

  const code = await runHostList([target], { io });

  assert.equal(code, 0);
  assert.match(io.stdout, /^Hosts declared in host-assets\.json \(project: /m);
  assert.match(io.stdout, /^host\s+name\s+components\s+selected$/m);
  assert.match(io.stdout, /^dsh\s+DeepSeek Harness\s+preset, hook\s+no$/m);
  assert.match(io.stdout, /^opencode\s+OpenCode\s+plugin\s+no$/m);
  // Every declared host has at least one component (a gate in
  // cli-registry.test.js asserts it), so no row can be component-less. This is
  // documentation of the invariant, not coverage: restoring the removed `-`
  // branch would still pass, because nothing can reach it.
  assert.doesNotMatch(io.stdout, /\s-\s/m);
});

test('host inspect --json reports one row per component across all hosts', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-inspect-');
  useEnv(t, {
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    QODER_CONFIG_DIR: join(home, 'qoder'),
    XDG_CONFIG_HOME: join(home, 'xdg'),
    ZCODE_HOME: join(home, 'zcode')
  });
  const io = createIo();

  const code = await main(['host', 'inspect', '--json'], { io });

  assert.equal(code, 0);
  const report = JSON.parse(io.stdout);
  assert.equal(report.schemaVersion, 1);
  const expected = loadHostAssetManifest().platforms.flatMap((platform) =>
    Object.keys(HOST_COMPONENTS[platform.id].components)
      .filter((name) => name !== 'all')
      .map((name) => `${platform.id}:${name}`)
  );
  assert.deepEqual(
    report.hosts.map((row) => `${row.id}:${row.component}`),
    expected
  );
  assert.ok(
    report.hosts.every((row) => row.status === 'missing'),
    'an empty machine has no installed host state'
  );
  assert.ok(
    report.hosts.every((row) => Object.hasOwn(row, 'detailPath')),
    'every component reports the diagnostic path field'
  );
});

test('host inspect accepts a host filter and rejects an unknown host', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-inspect-filter-');
  useEnv(t, { KIMI_CODE_HOME: join(home, 'kimi') });

  const io = createIo();
  assert.equal(await runHostInspect(['kimi-code', '--json'], { io, env: process.env }), 0);
  const filtered = JSON.parse(io.stdout);
  assert.deepEqual(
    filtered.hosts.map((row) => row.component),
    ['plugin', 'hook'],
    'the composite `all` component is not an installed artifact'
  );

  const errorIo = createIo();
  assert.equal(await main(['host', 'inspect', 'nope'], { io: errorIo }), 2);
  assert.match(errorIo.stderr, /Unknown host: nope/);
});

test('host list rejects a second positional argument', async () => {
  const io = createIo();

  await assert.rejects(
    () => runHostList(['one', 'two'], { io }),
    /Unexpected argument: two/
  );
});

// Every installer used to scan argv for the flags it knew and ignore the rest,
// so a typo silently ran the command as if the flag had not been passed.
test('every installer rejects an unknown flag instead of ignoring it', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-flags-');
  useEnv(t, {
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    XDG_CONFIG_HOME: join(home, 'xdg'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    QODER_CONFIG_DIR: join(home, 'qoder'),
    ZCODE_HOME: join(home, 'zcode')
  });

  const targets = [
    ['opencode'],
    ['claude-code'],
    ['codex'],
    ['zcode'],
    ['qoder'],
    ['kimi-code'],
    ['dsh', '--component', 'preset'],
    ['dsh', '--component', 'hook']
  ];
  for (const target of targets) {
    const io = createIo();
    const output = await captureConsole(() => main(['host', 'add', ...target, '--dry-run', '--bogus'], { io }));
    assert.equal(io.stderr, 'Unknown option: --bogus\n', `host add ${target.join(' ')} accepted --bogus`);
    assert.equal(output, '', `host add ${target.join(' ')} ran anyway`);
  }
});

// The kimi-code hook has no --force: installing always rewrites the shim and its
// block, so the flag was removed rather than kept as a no-op. It is now reached
// through --component, since the host's default is the combined component.
test('an installer rejects a flag it does not have', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-noforce-');
  useEnv(t, { KIMI_CODE_HOME: join(home, 'kimi') });

  const io = createIo();
  const output = await captureConsole(
    () => main(['host', 'add', 'kimi-code', '--component', 'hook', '--force'], { io })
  );

  assert.equal(io.stderr, 'Unknown option: --force\n');
  assert.equal(output, '');
});

// `cwf host add kimi-code` is the one step a machine needs: injection (the
// required half) and the bootstrap plugin together. The single-component paths
// stay available and stay separate.
test('host add kimi-code installs the hook and the plugin in one command', async (t) => {
  const home = await createKimiHome(t);

  const installed = await captureConsole(() => runHostAdd(['kimi-code']));

  const config = await readFile(kimiConfig(home), 'utf8');
  assert.match(config, /^\[\[hooks\]\]$/m);
  assert.ok(await exists(kimiShim(home)), 'hook shim missing after the combined install');
  assert.ok(await exists(kimiMarker(home)), 'hook version marker missing');
  const registry = await readJson(installedRegistryPath(home));
  assert.equal(registry.plugins.filter((entry) => entry.id === 'cowork-flow').length, 1);
  assert.match(installed, /Kimi Code hook shim installed/);
  assert.match(installed, /Kimi Code plugin installed/);
});

test('--component plugin installs the plugin alone and leaves config.toml untouched', async (t) => {
  const home = await createKimiHome(t);

  await captureConsole(() => runHostAdd(['kimi-code', '--component', 'plugin']));

  assert.equal(await exists(kimiConfig(home)), false, 'a plugin-only install wrote the hook into config.toml');
  assert.equal(await exists(kimiShim(home)), false, 'a plugin-only install wrote the hook shim');
  const registry = await readJson(installedRegistryPath(home));
  assert.ok(registry.plugins.some((entry) => entry.id === 'cowork-flow'));
});

test('--component hook installs the hook alone and leaves the plugin out', async (t) => {
  const home = await createKimiHome(t);

  await captureConsole(() => runHostAdd(['kimi-code', '--component', 'hook']));

  assert.match(await readFile(kimiConfig(home), 'utf8'), /^\[\[hooks\]\]$/m);
  assert.equal(await exists(installedRegistryPath(home)), false, 'a hook-only install wrote the plugin registry');
});

// The one flag the two installers disagree on: the combined component routes it
// to the plugin and keeps it away from the hook. The value form pins that
// routing — `--force` is boolean everywhere, so `--force=true` must reach the
// plugin's "--force does not take a value" rather than the hook's "Unknown option".
test('the combined component routes --force to the plugin segment only', async (t) => {
  await createKimiHome(t);

  const output = await captureConsole(() => runHostAdd(['kimi-code', '--force']));
  assert.match(output, /Kimi Code plugin/);

  let failure = null;
  const valueForm = await captureConsole(async () => {
    try {
      await runHostAdd(['kimi-code', '--force=true']);
    } catch (error) {
      failure = error;
    }
  });
  assert.match(failure?.message ?? '', /--force does not take a value/);
  assert.match(valueForm, /Kimi Code hook shim installed/);

  await assert.rejects(
    () => captureConsole(() => runHostAdd(['kimi-code', '--component', 'hook', '--force'])),
    /Unknown option: --force/
  );
});

test('the combined dry-run previews both segments and writes nothing', async (t) => {
  const home = await createKimiHome(t);

  const output = await captureConsole(() => runHostAdd(['kimi-code', '--dry-run']));

  assert.match(output, /\[dry-run\] Would install Kimi Code context hook/);
  assert.match(output, /\[dry-run\] Would install cowork-flow Kimi Code plugin/);
  assert.equal(await exists(kimiConfig(home)), false);
  assert.equal(await exists(installedRegistryPath(home)), false);
});

// One command to remove what one command installed, through either spelling.
test('host remove kimi-code uninstalls the hook and the plugin together', async (t) => {
  const home = await createKimiHome(t);
  await captureConsole(() => runHostAdd(['kimi-code']));

  await captureConsole(() => runHostRemove(['kimi-code']));

  assert.equal(await exists(kimiConfig(home)), false, 'the hook config survived the combined removal');
  assert.equal(await exists(kimiShim(home)), false, 'the hook shim survived the combined removal');
  const registry = await readJson(installedRegistryPath(home));
  assert.deepEqual(registry.plugins, [], 'the plugin record survived the combined removal');

  // `--uninstall` is documented as the same path, so it must be one.
  await captureConsole(() => runHostAdd(['kimi-code']));
  await captureConsole(() => runHostAdd(['kimi-code', '--uninstall']));
  assert.equal(await exists(kimiConfig(home)), false, 'host add --uninstall diverged from host remove');
  assert.deepEqual((await readJson(installedRegistryPath(home))).plugins, []);
});

// Two idempotent installers composed without a transaction: a second run has to
// converge rather than accumulate, since a rerun is the only recovery path.
test('the combined install converges on a second run', async (t) => {
  const home = await createKimiHome(t);

  await captureConsole(() => runHostAdd(['kimi-code']));
  const firstConfig = await readFile(kimiConfig(home), 'utf8');
  await captureConsole(() => runHostAdd(['kimi-code']));

  assert.equal(await readFile(kimiConfig(home), 'utf8'), firstConfig);
  const registry = await readJson(installedRegistryPath(home));
  assert.equal(registry.plugins.filter((entry) => entry.id === 'cowork-flow').length, 1);
});

// Fail-fast, hook first: when the plugin segment throws, the hook half stays
// done and says so — the error is not a rollback.
test('a failing plugin segment surfaces after the hook segment finished', async (t) => {
  const home = await createKimiHome(t);
  const registryPath = installedRegistryPath(home);
  await mkdir(join(home, 'plugins'), { recursive: true });
  await writeFile(registryPath, '{ definitely not JSON', 'utf8');

  let failure = null;
  const output = await captureConsole(async () => {
    try {
      await runHostAdd(['kimi-code']);
    } catch (error) {
      failure = error;
    }
  });

  assert.match(failure?.message ?? '', /not valid JSON/);
  assert.match(output, /Kimi Code hook shim installed/);
  assert.match(await readFile(kimiConfig(home), 'utf8'), /^\[\[hooks\]\]$/m);
  assert.equal(await readFile(registryPath, 'utf8'), '{ definitely not JSON');
});

// The shims and the new names must not drift apart: the old spelling is what
// users already have in shell history and scripts.
test('legacy host command names run the same code as the new ones', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-shim-');
  useEnv(t, { DSH_HOME: home });

  const shims = [
    { legacy: 'install-dsh-preset', modern: ['host', 'add', 'dsh', '--component', 'preset'] },
    { legacy: 'install-dsh-hook', modern: ['host', 'add', 'dsh', '--component', 'hook'] },
    { legacy: 'install-kimi-hook', modern: ['host', 'add', 'kimi-code', '--component', 'hook'] }
  ];
  for (const { legacy, modern } of shims) {
    const io = createIo();
    const modernIo = createIo();
    const legacyOutput = await captureConsole(() => main([legacy, '--dry-run'], { io }));
    const modernOutput = await captureConsole(() => main([...modern, '--dry-run'], { io: modernIo }));

    assert.equal(legacyOutput, modernOutput, `${legacy} and ${modern.join(' ')} diverge`);
    assert.match(io.stderr, new RegExp(`note: "cwf ${legacy}" is now "cwf ${modern.join(' ')}"`));
    assert.equal(modernIo.stderr, '');
  }
});
