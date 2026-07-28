import { spawn as defaultSpawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

export const CORE_TEMPLATE_TEST_MODULES = Object.freeze([
  'tests.test_state_store',
  'tests.test_state_migrations',
  'tests.test_task_creation',
  'tests.test_task_tree',
  'tests.test_decision_anchor',
  'tests.test_host_adapters',
  'tests.test_host_asset_manifest',
  'tests.test_skill_routing',
  'tests.test_task_navigation',
  'tests.test_workflow_parallel_sessions'
]);

const TEMPLATE_TEST_SUITES = new Set(['core', 'full']);

export function createTemplateTestTempRoot() {
  // Keep copied repositories away from workspace watchers and concurrent runs.
  return mkdtempSync(join(resolve(tmpdir()), 'cowork-flow-template-tests-'));
}

function normalizedSeed(seed) {
  return String(seed).replaceAll(/[^A-Za-z0-9._-]/g, '_');
}

function parseSuite(args) {
  let suite = 'core';
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--suite') {
      suite = args[index + 1];
      index += 1;
    } else if (arg.startsWith('--suite=')) {
      suite = arg.slice('--suite='.length);
    } else {
      throw new Error(`Unknown template test option: ${arg}`);
    }
  }
  if (!TEMPLATE_TEST_SUITES.has(suite)) {
    throw new Error('Template test suite must be one of: core, full');
  }
  return suite;
}

export function parseTemplateTestOptions(env = process.env, args = []) {
  const rawRepeat = env.COWORK_TEMPLATE_TEST_REPEAT ?? '1';
  const repeat = Number.parseInt(rawRepeat, 10);
  if (!Number.isInteger(repeat) || repeat < 1 || String(repeat) !== rawRepeat.trim()) {
    throw new Error('COWORK_TEMPLATE_TEST_REPEAT must be a positive integer');
  }
  return {
    repeat,
    seed: env.COWORK_TEMPLATE_TEST_SEED?.trim() || Date.now().toString(36),
    suite: parseSuite(args)
  };
}

function unittestArgs(suite) {
  if (suite === 'full') {
    return ['python', '-m', 'unittest', 'discover', 'tests', '-v'];
  }
  return ['python', '-m', 'unittest', ...CORE_TEMPLATE_TEST_MODULES, '-v'];
}

function runIteration({
  runner,
  iteration,
  repeat,
  seed,
  suite,
  tempDir,
  spawnImpl,
  platform,
  env,
  stderr
}) {
  return new Promise((resolveCode) => {
    let settled = false;
    const settle = (code) => {
      if (!settled) {
        settled = true;
        resolveCode(code);
      }
    };
    const child = spawnImpl(
      runner,
      unittestArgs(suite),
      {
        stdio: 'inherit',
        shell: platform === 'win32',
        env: {
          ...env,
          PYTHONDONTWRITEBYTECODE: '1',
          TMP: tempDir,
          TEMP: tempDir,
          TMPDIR: tempDir,
          COWORK_TEMPLATE_TEST_ITERATION: String(iteration),
          COWORK_TEMPLATE_TEST_REPEAT: String(repeat),
          COWORK_TEMPLATE_TEST_SEED: seed,
          COWORK_TEMPLATE_TEST_SUITE: suite
        }
      }
    );
    child.once('error', (error) => {
      stderr.write(`${error.message}\n`);
      settle(1);
    });
    child.once('close', (code) => settle(code ?? 1));
  });
}

export async function runTemplateTests({
  repeat,
  seed,
  suite = 'core',
  runner,
  tempRoot,
  spawnImpl = defaultSpawn,
  platform = process.platform,
  env = process.env,
  stderr = process.stderr
}) {
  rmSync(tempRoot, { recursive: true, force: true });
  mkdirSync(tempRoot, { recursive: true });

  for (let iteration = 1; iteration <= repeat; iteration += 1) {
    const tempDir = resolve(
      tempRoot,
      `${normalizedSeed(seed)}-${String(iteration).padStart(2, '0')}`
    );
    rmSync(tempDir, { recursive: true, force: true });
    mkdirSync(tempDir, { recursive: true });
    const code = await runIteration({
      runner,
      iteration,
      repeat,
      seed,
      suite,
      tempDir,
      spawnImpl,
      platform,
      env,
      stderr
    });
    if (code !== 0) {
      stderr.write(
        `[template-tests] suite=${suite} iteration=${iteration}/${repeat} seed=${seed} `
        + `exit=${code} temp=${tempDir}\n`
      );
      return code;
    }
    rmSync(tempDir, { recursive: true, force: true });
  }

  rmSync(tempRoot, { recursive: true, force: true });
  return 0;
}
