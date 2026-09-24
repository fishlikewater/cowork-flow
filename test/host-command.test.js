import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { HOST_COMPONENTS, runHostAdd, runHostList, runHostRemove } from '../src/commands/host.js';
import { loadHostAssetManifest } from '../src/lib/host-assets.js';

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
    { argv: ['kimi-code'], expect: /Kimi Code context hook/ }
  ];
  for (const { argv, expect } of cases) {
    const output = await captureConsole(() => runHostAdd([...argv, '--dry-run']));
    assert.match(output, expect, `host add ${argv.join(' ')} did not reach its installer`);
  }
});

// dsh is the one host with two components, so it is where a default that
// silently picked the wrong one would show up.
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
  assert.match(kimiAlias, /Kimi Code context hook/);
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
    { argv: ['kimi-code'], expect: /Would uninstall Kimi Code context hook/ },
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

test('host list prints a table by default and flags hosts without components', async (t) => {
  const target = await createTempDir(t, 'cowork-flow-host-table-');
  const io = createIo();

  const code = await runHostList([target], { io });

  assert.equal(code, 0);
  assert.match(io.stdout, /^Hosts declared in host-assets\.json \(project: /m);
  assert.match(io.stdout, /^host\s+name\s+components\s+selected$/m);
  assert.match(io.stdout, /^dsh\s+DeepSeek Harness\s+preset, hook\s+no$/m);
  assert.match(io.stdout, /^opencode\s+OpenCode\s+plugin\s+no$/m);
  // Every declared host now has a machine-level component, so no row can show
  // the "no component" marker. This assertion makes that a fact the suite
  // tracks: the day a host is declared without one, it fails and the marker's
  // rendering gets its coverage back.
  assert.doesNotMatch(io.stdout, /\s-\s/m);
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

// kimi-code has no --force: installing always rewrites the shim and its block,
// so the flag was removed rather than kept as a no-op.
test('an installer rejects a flag it does not have', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-noforce-');
  useEnv(t, { KIMI_CODE_HOME: join(home, 'kimi') });

  const io = createIo();
  const output = await captureConsole(() => main(['host', 'add', 'kimi-code', '--force'], { io }));

  assert.equal(io.stderr, 'Unknown option: --force\n');
  assert.equal(output, '');
});

// The shims and the new names must not drift apart: the old spelling is what
// users already have in shell history and scripts.
test('legacy host command names run the same code as the new ones', async (t) => {
  const home = await createTempDir(t, 'cowork-flow-host-shim-');
  useEnv(t, { DSH_HOME: home });

  const shims = [
    { legacy: 'install-dsh-preset', modern: ['host', 'add', 'dsh', '--component', 'preset'] },
    { legacy: 'install-dsh-hook', modern: ['host', 'add', 'dsh', '--component', 'hook'] },
    { legacy: 'install-kimi-hook', modern: ['host', 'add', 'kimi-code'] }
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
