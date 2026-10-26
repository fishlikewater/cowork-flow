import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

import { main } from '../src/cli.js';
import { runHostAdd, runHostRemove } from '../src/commands/host.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { createTempDir } from './helpers/fs.js';

const execFileAsync = promisify(execFile);
const REPO_CLI = fileURLToPath(new URL('../bin/cowork-flow.js', import.meta.url));

const HOME_KEYS = [
  'CLAUDE_CONFIG_DIR',
  'CODEX_HOME',
  'COWORK_FLOW_CLI',
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

// The installers and doctor both print with console.log.
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

function pythonExecutable() {
  return process.env.COWORK_FLOW_PYTHON || process.env.PYTHON || 'python';
}

async function initProject(t, host) {
  const root = await createTempDir(t);
  const target = join(root, 'project');
  const io = createIo();
  const code = await main(
    ['project', 'init', target, '--host', host, '--developer', `e2e-${host}`],
    { io }
  );
  assert.equal(code, 0, io.stderr);
  return target;
}

async function doctorIssues(project) {
  const runner = join(project, '.cowork-flow', 'scripts', 'run.py');
  let stdout;
  try {
    ({ stdout } = await execFileAsync(
      pythonExecutable(),
      [runner, 'doctor', '--all', '--json'],
      { cwd: project, encoding: 'utf8' }
    ));
  } catch (error) {
    // Unrelated health checks can make doctor exit non-zero; its JSON report
    // is still the fact under test.
    if (typeof error.stdout !== 'string' || !error.stdout.trim()) {
      throw error;
    }
    stdout = error.stdout;
  }
  return JSON.parse(stdout).issues;
}

async function install(host) {
  await captureConsole(() => runHostAdd([host]));
}

async function remove(host) {
  await captureConsole(() => runHostRemove([host]));
}

test('qoder install is visible to doctor and removal is observable', async (t) => {
  const home = await createTempDir(t);
  const qoderHome = join(home, 'qoder');
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    QODER_CONFIG_DIR: qoderHome
  });
  const project = await initProject(t, 'qoder');
  const { version } = await readPackageInfo();

  await install('qoder');

  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.qoderPlugin,
    [],
    'a fresh qoder install must be clean for the qoder plugin contract'
  );
  const registry = JSON.parse(
    await readFile(join(qoderHome, 'plugins', 'installed_plugins_v2.json'), 'utf8')
  );
  assert.equal(
    registry.plugins['cowork-flow@cowork-flow-local'][0].version,
    version,
    'doctor must see the version the installer recorded'
  );

  await remove('qoder');

  const removedIssues = await doctorIssues(project);
  assert.ok(
    removedIssues.qoderPlugin.some((issue) => issue.code === 'PLUGIN-NOT-INSTALLED'),
    `removal must be observable, got ${JSON.stringify(removedIssues.qoderPlugin)}`
  );
});

test('zcode install is visible to doctor and removal is observable', async (t) => {
  const home = await createTempDir(t);
  const zcodeHome = join(home, 'zcode');
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    ZCODE_HOME: zcodeHome
  });
  const project = await initProject(t, 'zcode');
  const { version } = await readPackageInfo();

  await install('zcode');

  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.zcodePlugin,
    [],
    'a fresh zcode install must be clean for the zcode plugin contract'
  );
  const marketplace = JSON.parse(
    await readFile(
      join(
        zcodeHome,
        'cli',
        'plugins',
        'marketplaces',
        'cowork-flow-local',
        'marketplace.json'
      ),
      'utf8'
    )
  );
  const entry = marketplace.plugins.find((plugin) => plugin.name === 'cowork-flow');
  assert.equal(
    entry.version,
    version,
    'doctor must see the version the marketplace records'
  );

  await remove('zcode');

  const removedIssues = await doctorIssues(project);
  assert.ok(
    removedIssues.zcodePlugin.some((issue) => issue.code === 'PLUGIN-NOT-INSTALLED'),
    `removal must be observable, got ${JSON.stringify(removedIssues.zcodePlugin)}`
  );
});

test('codex install is visible to doctor once the host registers the marketplace', async (t) => {
  const home = await createTempDir(t);
  const codexHome = join(home, 'codex');
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    CODEX_HOME: codexHome
  });
  const project = await initProject(t, 'codex');

  // Without a codex binary the installer only materializes the marketplace;
  // the registration itself is the host's job, so record what it writes.
  await install('codex');
  const source = join(codexHome, 'plugins', 'marketplaces', 'cowork-flow-local');
  await writeFile(
    join(codexHome, 'config.toml'),
    [
      '[marketplaces.cowork-flow-local]',
      `source = '${source}'`,
      '',
      '[plugins."cowork-flow@cowork-flow-local"]',
      'enabled = true'
    ].join('\n') + '\n',
    'utf8'
  );

  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.codexPlugin,
    [],
    'a registered codex marketplace with the installer payload must be clean'
  );
});

test('claude-code install is visible to doctor and removal is observable', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    CLAUDE_CONFIG_DIR: join(home, 'claude')
  });
  const project = await initProject(t, 'claude-code');

  await install('claude-code');
  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.claudeCodePlugin,
    [],
    'a fresh claude-code install must be clean for the claude-code plugin contract'
  );

  await remove('claude-code');
  const removedIssues = await doctorIssues(project);
  assert.ok(
    removedIssues.claudeCodePlugin.some((issue) => issue.code === 'PLUGIN-NOT-INSTALLED'),
    `removal must be observable, got ${JSON.stringify(removedIssues.claudeCodePlugin)}`
  );
});

test('opencode install is visible to doctor and removal is observable', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    XDG_CONFIG_HOME: join(home, 'xdg')
  });
  const project = await initProject(t, 'opencode');

  await install('opencode');
  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.opencodePlugin,
    [],
    'a fresh opencode install must be clean for the opencode plugin contract'
  );

  await remove('opencode');
  const removedIssues = await doctorIssues(project);
  assert.ok(
    removedIssues.opencodePlugin.some((issue) => issue.code === 'PLUGIN-NOT-INSTALLED'),
    `removal must be observable, got ${JSON.stringify(removedIssues.opencodePlugin)}`
  );
});

test('kimi-code install is visible to doctor and removal is observable', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    KIMI_CODE_HOME: join(home, 'kimi')
  });
  const project = await initProject(t, 'kimi-code');

  await install('kimi-code');
  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.kimiCodePlugin,
    [],
    'a fresh kimi-code plugin install must be clean'
  );
  assert.deepEqual(
    installedIssues.kimiHook,
    [],
    'a fresh kimi-code hook install must be clean'
  );

  await remove('kimi-code');
  const removedIssues = await doctorIssues(project);
  assert.ok(
    removedIssues.kimiCodePlugin.some((issue) => issue.code === 'PLUGIN-NOT-INSTALLED'),
    `plugin removal must be observable, got ${JSON.stringify(removedIssues.kimiCodePlugin)}`
  );
});

test('dsh preset install is visible to doctor and removal is silent', async (t) => {
  const home = await createTempDir(t);
  useEnv(t, {
    HOME: home,
    USERPROFILE: home,
    COWORK_FLOW_CLI: REPO_CLI,
    DSH_HOME: join(home, 'dsh')
  });
  const project = await initProject(t, 'dsh');

  await install('dsh');
  const installedIssues = await doctorIssues(project);
  assert.deepEqual(
    installedIssues.dshPreset,
    [],
    'a fresh dsh preset install must be clean'
  );

  await remove('dsh');
  const removedIssues = await doctorIssues(project);
  assert.deepEqual(
    removedIssues.dshPreset,
    [],
    'an absent preset stays silent by contract'
  );
});
