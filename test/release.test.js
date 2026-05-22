import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

async function createFakeNpm(t, options = {}) {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-release-test-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  const binDir = join(tempDir, 'bin');
  const logPath = join(tempDir, 'commands.log');
  await mkdir(binDir);
  await writeFile(logPath, '', 'utf8');

  const failWhen = options.failWhen ?? '';
  const fakeNpmPath = join(binDir, 'npm');
  await writeFile(
    fakeNpmPath,
    [
      '#!/bin/sh',
      `printf '%s\\n' "$*" >> "${logPath}"`,
      `if [ "$*" = "${failWhen}" ]; then exit 7; fi`,
      'exit 0'
    ].join('\n'),
    { encoding: 'utf8', mode: 0o755 }
  );

  return {
    logPath,
    env: {
      ...process.env,
      PATH: `${binDir}${delimiter}${process.env.PATH}`
    }
  };
}

async function readCommands(logPath) {
  const raw = await readFile(logPath, 'utf8');
  return raw.trim().split('\n').filter(Boolean);
}

test('release shell script defaults to patch and runs verification before publish', async (t) => {
  const fakeNpm = await createFakeNpm(t);

  const result = await execFileAsync('sh', ['scripts/release.sh'], {
    cwd: packageRoot,
    env: fakeNpm.env,
    encoding: 'utf8'
  });

  assert.match(result.stdout, /> npm run test:all/);
  assert.deepEqual(await readCommands(fakeNpm.logPath), [
    'run test:all',
    'version patch',
    'publish'
  ]);
});

test('release shell script accepts explicit npm version type', async (t) => {
  const fakeNpm = await createFakeNpm(t);

  await execFileAsync('sh', ['scripts/release.sh', 'minor'], {
    cwd: packageRoot,
    env: fakeNpm.env,
    encoding: 'utf8'
  });

  assert.deepEqual(await readCommands(fakeNpm.logPath), [
    'run test:all',
    'version minor',
    'publish'
  ]);
});

test('release shell script stops after the first failed command', async (t) => {
  const fakeNpm = await createFakeNpm(t, { failWhen: 'run test:all' });

  await assert.rejects(
    execFileAsync('sh', ['scripts/release.sh', 'major'], {
      cwd: packageRoot,
      env: fakeNpm.env,
      encoding: 'utf8'
    }),
    (error) => error.code === 7
  );

  assert.deepEqual(await readCommands(fakeNpm.logPath), ['run test:all']);
});

test('release shell script rejects unsupported version type', async (t) => {
  const fakeNpm = await createFakeNpm(t);

  await assert.rejects(
    execFileAsync('sh', ['scripts/release.sh', 'banana'], {
      cwd: packageRoot,
      env: fakeNpm.env,
      encoding: 'utf8'
    }),
    (error) => {
      assert.equal(error.code, 1);
      assert.match(error.stderr, /Unsupported release type: banana/);
      assert.match(error.stderr, /major minor patch/);
      return true;
    }
  );

  assert.deepEqual(await readCommands(fakeNpm.logPath), []);
});
