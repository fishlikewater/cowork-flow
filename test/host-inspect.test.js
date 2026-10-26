import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import { runHostAdd, runHostInspect } from '../src/commands/host.js';
import {
  INSPECT_SCHEMA_VERSION,
  INSPECT_STATUSES,
  renderInspectLine
} from '../src/commands/host-inspect.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { createTempDir } from './helpers/fs.js';

const HOME_KEYS = [
  'CLAUDE_CONFIG_DIR',
  'CODEX_HOME',
  'COWORK_FLOW_CODEX',
  'DSH_HOME',
  'HOME',
  'KIMI_CODE_HOME',
  'QODER_CONFIG_DIR',
  'USERPROFILE',
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

async function inspectIo(args) {
  const io = createIo();
  const code = await runHostInspect(args, { io, env: process.env });
  return { code, io, report: io.stdout.trim() ? JSON.parse(io.stdout) : null };
}

function row(report, id) {
  return report.hosts.find((entry) => entry.id === id);
}

async function install(host) {
  await captureConsole(() => runHostAdd([host]));
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

async function writeJson(path, value) {
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function snapshot(dir) {
  const entries = [];
  async function walk(current) {
    for (const entry of await readdir(current, { withFileTypes: true })) {
      const path = join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(path);
      } else {
        const digest = createHash('sha256').update(await readFile(path)).digest('hex');
        entries.push(`${path}:${digest}`);
      }
    }
  }
  await walk(dir);
  return entries.sort();
}

function qoderPaths(home) {
  return {
    registry: join(home, 'plugins', 'installed_plugins_v2.json'),
    settings: join(home, 'settings.json')
  };
}

function zcodePaths(home) {
  return {
    marketplace: join(
      home,
      'cli',
      'plugins',
      'marketplaces',
      'cowork-flow-local',
      'marketplace.json'
    )
  };
}

test('inspect reports installed qoder and zcode with version and payload path', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    QODER_CONFIG_DIR: join(home, 'qoder'),
    ZCODE_HOME: join(home, 'zcode'),
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    XDG_CONFIG_HOME: join(home, 'xdg')
  });
  await install('qoder');
  await install('zcode');
  const { version } = await readPackageInfo();

  const { code, report } = await inspectIo(['--json']);

  assert.equal(code, 0);
  assert.equal(report.schemaVersion, 1);
  assert.equal(report.cliVersion, version);
  const qoder = row(report, 'qoder');
  assert.equal(qoder.status, 'installed');
  assert.equal(qoder.version, version);
  assert.match(qoder.registeredSource, /installed_plugins_v2\.json$/);
  assert.equal(qoder.enabled, true);
  assert.ok(qoder.payloadPath.endsWith(join('cowork-flow', version)));
  assert.ok(
    qoder.detailPath.endsWith(join('cowork-flow', version, '.qoder-plugin', 'plugin.json')),
    qoder.detailPath
  );
  const zcode = row(report, 'zcode');
  assert.equal(zcode.status, 'installed');
  assert.equal(zcode.version, version);
  assert.match(zcode.registeredSource, /marketplace\.json$/);
  assert.equal(
    zcode.payloadPath,
    join(home, 'zcode', 'cli', 'plugins', 'cache', 'cowork-flow-local', 'cowork-flow', version)
      .split('\\')
      .join('/')
  );
  assert.ok(
    zcode.detailPath.endsWith(join('.zcode-plugin', 'plugin.json')),
    zcode.detailPath
  );
  assert.equal(row(report, 'codex').status, 'missing');
});

test('inspect reports missing, stale, broken and disabled without failing', async (t) => {
  const home = await createTempDir(t);
  const qoderHome = join(home, 'qoder');
  const zcodeHome = join(home, 'zcode');
  useEnv(t, {
    QODER_CONFIG_DIR: qoderHome,
    ZCODE_HOME: zcodeHome,
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    XDG_CONFIG_HOME: join(home, 'xdg')
  });
  const { version } = await readPackageInfo();

  const missing = await inspectIo(['--json']);
  assert.equal(missing.code, 0);
  assert.equal(row(missing.report, 'qoder').status, 'missing');
  assert.equal(row(missing.report, 'qoder').detailPath, qoderPaths(qoderHome).registry);
  assert.equal(row(missing.report, 'zcode').status, 'missing');
  assert.equal(row(missing.report, 'zcode').detailPath, zcodePaths(zcodeHome).marketplace);

  await install('qoder');
  await install('zcode');
  const qoder = qoderPaths(qoderHome);
  const zcode = zcodePaths(zcodeHome);

  const registry = await readJson(qoder.registry);
  registry.plugins['cowork-flow@cowork-flow-local'][0].version = '0.0.1';
  await writeJson(qoder.registry, registry);
  const stale = await inspectIo(['qoder', '--json']);
  assert.equal(stale.code, 0, 'a stale install is data, not a command failure');
  const staleQoder = row(stale.report, 'qoder');
  assert.equal(staleQoder.status, 'stale');
  assert.equal(staleQoder.version, '0.0.1');
  assert.ok(
    staleQoder.detailPath.endsWith(join('.qoder-plugin', 'plugin.json')),
    staleQoder.detailPath
  );
  assert.match(staleQoder.reason, new RegExp(version.replaceAll('.', '\\.')));

  const market = await readJson(zcode.marketplace);
  const payloadPath = market.plugins.find((plugin) => plugin.name === 'cowork-flow').source.path;
  await rm(join(payloadPath, '.zcode-plugin', 'plugin.json'), { force: true });
  const broken = await inspectIo(['zcode', '--json']);
  assert.equal(broken.code, 0, 'a broken install is data, not a command failure');
  const brokenZcode = row(broken.report, 'zcode');
  assert.equal(brokenZcode.status, 'broken');
  assert.equal(brokenZcode.payloadPath, payloadPath);
  assert.equal(brokenZcode.detailPath, join(payloadPath, '.zcode-plugin', 'plugin.json'));
  assert.match(brokenZcode.reason, /payload manifest has no version/);

  const settings = await readJson(qoder.settings);
  settings.enabledPlugins['cowork-flow@cowork-flow-local'] = false;
  await writeJson(qoder.settings, settings);
  registry.plugins['cowork-flow@cowork-flow-local'][0].version = version;
  await writeJson(qoder.registry, registry);
  const disabled = await inspectIo(['qoder', '--json']);
  const disabledQoder = row(disabled.report, 'qoder');
  assert.equal(disabledQoder.status, 'installed');
  assert.equal(disabledQoder.enabled, false);
  assert.equal(disabledQoder.detailPath, qoder.settings);
  assert.match(disabledQoder.reason, /enable flag is not true/);

  const codex = await inspectIo(['codex', '--json']);
  assert.equal(codex.code, 0);
  assert.equal(row(codex.report, 'codex').status, 'missing');
  assert.equal(row(codex.report, 'codex').reason, 'marketplace is not registered');
});

test('inspect reports codex broken with the missing manifest path', async (t) => {
  const home = await createTempDir(t);
  const codexHome = join(home, 'codex');
  const source = join(codexHome, 'plugins', 'marketplaces', 'cowork-flow-local');
  const payload = join(source, 'plugins', 'cowork-flow');
  const manifest = join(payload, '.codex-plugin', 'plugin.json');
  useEnv(t, { CODEX_HOME: codexHome });
  await mkdir(join(payload, '.codex-plugin'), { recursive: true });
  await writeFile(
    join(codexHome, 'config.toml'),
    [
      '[marketplaces.cowork-flow-local]',
      'source_type = "local"',
      `source = '${source}'`,
      '',
      '[plugins."cowork-flow@cowork-flow-local"]',
      'enabled = true',
      ''
    ].join('\n'),
    'utf8'
  );

  const { code, report } = await inspectIo(['codex', '--json']);

  assert.equal(code, 0);
  const codex = row(report, 'codex');
  assert.equal(codex.status, 'broken');
  assert.equal(codex.payloadPath, payload);
  assert.equal(codex.detailPath, manifest);
  assert.equal(codex.reason, 'missing .codex-plugin/plugin.json');
});

test('inspect report locks schemaVersion 1, the row fields and the status enum', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    QODER_CONFIG_DIR: join(home, 'qoder'),
    XDG_CONFIG_HOME: join(home, 'xdg'),
    ZCODE_HOME: join(home, 'zcode')
  });

  const { report } = await inspectIo(['--json']);

  assert.equal(INSPECT_SCHEMA_VERSION, 1);
  assert.equal(report.schemaVersion, INSPECT_SCHEMA_VERSION);
  assert.deepEqual(
    [...INSPECT_STATUSES].sort(),
    ['broken', 'installed', 'missing', 'stale', 'unsupported']
  );
  for (const row of report.hosts) {
    assert.deepEqual(
      Object.keys(row).sort(),
      [
        'component',
        'detailPath',
        'displayName',
        'enabled',
        'id',
        'payloadPath',
        'reason',
        'registeredSource',
        'status',
        'version'
      ],
      `${row.id}:${row.component} must keep the contract row shape`
    );
    assert.ok(
      INSPECT_STATUSES.includes(row.status),
      `${row.id}:${row.component} reported ${row.status}`
    );
  }
});

test('inspect text output prefers detailPath and falls back to payloadPath', () => {
  const missing = renderInspectLine({
    id: 'codex',
    displayName: 'Codex',
    component: 'plugin',
    status: 'missing',
    version: null,
    payloadPath: null,
    detailPath: 'C:/codex/config.toml',
    enabled: null,
    reason: 'marketplace is not registered'
  });
  assert.ok(missing.includes(' - C:/codex/config.toml; marketplace is not registered'), missing);

  const broken = renderInspectLine({
    id: 'opencode',
    displayName: 'OpenCode',
    component: 'plugin',
    status: 'broken',
    version: null,
    payloadPath: 'C:/payload',
    detailPath: 'C:/payload/cowork-flow.js',
    enabled: null,
    reason: 'no plugin file'
  });
  assert.ok(broken.includes(' - C:/payload/cowork-flow.js; no plugin file'), broken);
  assert.ok(!broken.includes(' - C:/payload;'), broken);

  const fallback = renderInspectLine({
    id: 'qoder',
    displayName: 'Qoder',
    component: 'plugin',
    status: 'installed',
    version: null,
    payloadPath: 'C:/payload',
    detailPath: null,
    enabled: null,
    reason: null
  });
  assert.ok(fallback.includes(' - C:/payload'), fallback);
});

test('inspect reports both dsh components once each is installed', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, { DSH_HOME: join(home, 'dsh') });
  await captureConsole(() => runHostAdd(['dsh']));
  await captureConsole(() => runHostAdd(['dsh', '--component', 'hook']));

  const { code, report } = await inspectIo(['dsh', '--json']);

  assert.equal(code, 0);
  const rows = report.hosts.filter((entry) => entry.id === 'dsh');
  assert.deepEqual(
    rows.map((entry) => entry.component),
    ['preset', 'hook'],
    'the composite `all` component never becomes a row'
  );
  assert.ok(rows.every((entry) => entry.status === 'installed'), rows);
});

test('inspect rejects an unknown host with a usage error', async () => {
  const io = createIo();
  const code = await main(['host', 'inspect', 'not-a-host'], { io });

  assert.equal(code, 2);
  assert.match(io.stderr, /Unknown host: not-a-host/);
});

test('inspect does not write to the host configuration', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    QODER_CONFIG_DIR: join(home, 'qoder'),
    ZCODE_HOME: join(home, 'zcode'),
    CLAUDE_CONFIG_DIR: join(home, 'claude'),
    CODEX_HOME: join(home, 'codex'),
    DSH_HOME: join(home, 'dsh'),
    KIMI_CODE_HOME: join(home, 'kimi'),
    XDG_CONFIG_HOME: join(home, 'xdg')
  });
  await install('qoder');
  await install('zcode');
  const before = await snapshot(home);

  await inspectIo(['--json']);
  await inspectIo(['qoder', '--json']);
  await inspectIo(['zcode', '--json']);

  assert.deepEqual(await snapshot(home), before);
});
