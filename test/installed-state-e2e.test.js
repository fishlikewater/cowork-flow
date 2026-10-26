import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { main } from '../src/cli.js';
import { runHostAdd, runHostRemove } from '../src/commands/host.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { createTempDir } from './helpers/fs.js';

const execFileAsync = promisify(execFile);

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
