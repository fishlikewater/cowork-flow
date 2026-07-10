import { spawn as defaultSpawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

function normalizedSeed(seed) {
  return String(seed).replaceAll(/[^A-Za-z0-9._-]/g, '_');
}

export function parseTemplateTestOptions(env = process.env) {
  const rawRepeat = env.COWORK_TEMPLATE_TEST_REPEAT ?? '1';
  const repeat = Number.parseInt(rawRepeat, 10);
  if (!Number.isInteger(repeat) || repeat < 1 || String(repeat) !== rawRepeat.trim()) {
    throw new Error('COWORK_TEMPLATE_TEST_REPEAT must be a positive integer');
  }
  return {
    repeat,
    seed: env.COWORK_TEMPLATE_TEST_SEED?.trim() || Date.now().toString(36)
  };
}

function runIteration({
  runner,
  iteration,
  repeat,
  seed,
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
      ['python', '-m', 'unittest', 'discover', 'tests', '-v'],
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
          COWORK_TEMPLATE_TEST_SEED: seed
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
      tempDir,
      spawnImpl,
      platform,
      env,
      stderr
    });
    if (code !== 0) {
      stderr.write(
        `[template-tests] iteration=${iteration}/${repeat} seed=${seed} `
        + `exit=${code} temp=${tempDir}\n`
      );
      return code;
    }
    rmSync(tempDir, { recursive: true, force: true });
  }

  rmSync(tempRoot, { recursive: true, force: true });
  return 0;
}
