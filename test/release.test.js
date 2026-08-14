import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);
const shellRunner = (() => {
  for (const candidate of ['sh', 'bash']) {
    try {
      execFileSync(candidate, ['-c', 'exit 0'], { stdio: 'ignore' });
      return candidate;
    } catch {
      // Try next shell candidate.
    }
  }
  return null;
})();

function skipWithoutShell(t) {
  if (shellRunner === null) {
    t.skip('POSIX shell is not available on this host');
    return true;
  }
  return false;
}

async function createReleaseProject(t) {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-release-project-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  const repo = join(tempDir, 'repo');
  await mkdir(join(repo, 'scripts'), { recursive: true });
  await mkdir(join(repo, 'template', '.cowork-flow'), { recursive: true });
  await writeFile(
    join(repo, 'scripts', 'release.sh'),
    await readFile(join(packageRoot, 'scripts', 'release.sh'), 'utf8'),
    { encoding: 'utf8', mode: 0o755 }
  );
  await writeFile(
    join(repo, 'package.json'),
    `${JSON.stringify({ name: 'cowork-flow', version: '0.0.5' }, null, 2)}\n`,
    'utf8'
  );
  await writeFile(
    join(repo, 'package-lock.json'),
    `${JSON.stringify({ name: 'cowork-flow', version: '0.0.5', packages: { '': { version: '0.0.5' } } }, null, 2)}\n`,
    'utf8'
  );
  await writeFile(join(repo, 'template', '.cowork-flow', '.version'), '0.0.5\n', 'utf8');
  return repo;
}

async function createFakeCommands(t, options = {}) {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-release-test-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  const binDir = join(tempDir, 'bin');
  const logPath = join(tempDir, 'commands.log');
  await mkdir(binDir);
  await writeFile(logPath, '', 'utf8');

  const failWhen = options.failWhen ?? '';
  await writeFile(
    join(binDir, 'npm'),
    [
      '#!/bin/sh',
      `printf 'npm %s\n' "$*" >> "${logPath}"`,
      `if [ "npm $*" = "${failWhen}" ]; then exit 7; fi`,
      'if [ "$1" = "version" ]; then',
      "  node - \"$2\" <<\'NODE\'",
      'const fs = require("fs");',
      'const releaseType = process.argv[2];',
      'const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));',
      'pkg.version = releaseType === "minor" ? "0.1.0" : "0.0.6";',
      'fs.writeFileSync("package.json", `${JSON.stringify(pkg, null, 2)}\\n`);',
      'const lock = JSON.parse(fs.readFileSync("package-lock.json", "utf8"));',
      'lock.version = pkg.version;',
      'lock.packages[""].version = pkg.version;',
      'fs.writeFileSync("package-lock.json", `${JSON.stringify(lock, null, 2)}\\n`);',
      'NODE',
      'fi',
      'exit 0'
    ].join('\n'),
    { encoding: 'utf8', mode: 0o755 }
  );

  await writeFile(
    join(binDir, 'git'),
    [
      '#!/bin/sh',
      `printf 'git %s\n' "$*" >> "${logPath}"`,
      `if [ "git $*" = "${failWhen}" ]; then exit 7; fi`,
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

test('release shell script defaults to patch and syncs template version before publish', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);
  const repo = await createReleaseProject(t);

  const result = await execFileAsync(shellRunner, ['scripts/release.sh'], {
    cwd: repo,
    env: fakeCommands.env,
    encoding: 'utf8'
  });

  assert.match(result.stdout, /> npm run source:refresh/);
  assert.match(result.stdout, /> npm run test:all/);
  assert.equal(await readFile(join(repo, 'template', '.cowork-flow', '.version'), 'utf8'), '0.0.6\n');
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'npm version patch --no-git-tag-version',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.0.6',
    'git tag v0.0.6',
    'npm publish'
  ]);
});

test('release shell script accepts explicit npm version type', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);
  const repo = await createReleaseProject(t);

  await execFileAsync(shellRunner, ['scripts/release.sh', 'minor'], {
    cwd: repo,
    env: fakeCommands.env,
    encoding: 'utf8'
  });

  assert.equal(await readFile(join(repo, 'template', '.cowork-flow', '.version'), 'utf8'), '0.1.0\n');
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'npm version minor --no-git-tag-version',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.1.0',
    'git tag v0.1.0',
    'npm publish'
  ]);
});

test('release shell script stops after the first failed command', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, { failWhen: 'npm run test:all' });

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', 'major'], {
      cwd: await createReleaseProject(t),
      env: fakeCommands.env,
      encoding: 'utf8'
    }),
    (error) => error.code === 7
  );

  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all'
  ]);
});

test('release shell script stops when the skill replica refresh fails', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, { failWhen: 'npm run source:refresh' });

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', 'patch'], {
      cwd: await createReleaseProject(t),
      env: fakeCommands.env,
      encoding: 'utf8'
    }),
    (error) => error.code === 7
  );

  assert.deepEqual(await readCommands(fakeCommands.logPath), ['npm run source:refresh']);
});

test('release shell script rejects unsupported version type', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', 'banana'], {
      cwd: await createReleaseProject(t),
      env: fakeCommands.env,
      encoding: 'utf8'
    }),
    (error) => {
      assert.equal(error.code, 1);
      assert.match(error.stderr, /Unsupported release type: banana/);
      assert.match(error.stderr, /major minor patch/);
      return true;
    }
  );

  assert.deepEqual(await readCommands(fakeCommands.logPath), []);
});
