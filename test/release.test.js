import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';
import { shellRunner, skipWithoutShell } from './shell-capability.js';

const execFileAsync = promisify(execFile);

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
  // The release gate requires a changelog entry for the post-bump version;
  // fake bump targets (patch -> 0.0.6, minor -> 0.1.0) and exact-mode
  // targets (0.0.7, 0.0.5 already at current) are all covered.
  await writeFile(
    join(repo, 'CHANGELOG.md'),
    '# Changelog\n\n## 0.1.0 - placeholder\n\nplaceholder\n\n## 0.0.7 - placeholder\n\nplaceholder\n\n## 0.0.5 - placeholder\n\nplaceholder\n\n## 0.0.6 - placeholder\n\nplaceholder\n',
    'utf8'
  );
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
  const commitNoop = options.commitNoop ?? false;
  const tagExists = options.tagExists ?? false;
  const tagMismatch = options.tagMismatch ?? false;
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
      'pkg.version = /^[0-9]+\\.[0-9]+\\.[0-9]+/.test(releaseType) ? releaseType : (releaseType === "minor" ? "0.1.0" : "0.0.6");',
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
      `if [ "$1" != "rev-parse" ]; then printf 'git %s\n' "$*" >> "${logPath}"; fi`,
      `if [ "git $*" = "${failWhen}" ]; then exit 7; fi`,
      `if [ "$1" = "rev-parse" ]; then`,
      '  case "$*" in',
      '    *"refs/tags/"*)',
      `      if [ "${tagExists ? '1' : '0'}" = "1" ]; then`,
      `        if [ "${tagMismatch ? '1' : '0'}" = "1" ]; then echo "2222222222222222222222222222222222"; else echo "1111111111111111111111111111111111"; fi`,
      '      else',
      '        exit 1',
      '      fi',
      '      ;;',
      '    *) echo "1111111111111111111111111111111111" ;;',
      '  esac',
      '  exit 0',
      'fi',
      ...(commitNoop
        ? [
            'if [ "$1" = "commit" ]; then',
            '  echo "On branch master"',
            '  echo "nothing to commit, working tree clean"',
            '  exit 1',
            'fi'
          ]
        : []),
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

test('release shell script publishes an explicit --version without bumping', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);
  const repo = await createReleaseProject(t);

  const result = await execFileAsync(
    shellRunner,
    ['scripts/release.sh', '--version', '0.0.7'],
    { cwd: repo, env: fakeCommands.env, encoding: 'utf8' }
  );

  assert.match(result.stdout, /> npm version 0.0.7 --no-git-tag-version/);
  assert.equal(JSON.parse(await readFile(join(repo, 'package.json'), 'utf8')).version, '0.0.7');
  assert.equal(await readFile(join(repo, 'template', '.cowork-flow', '.version'), 'utf8'), '0.0.7\n');
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'npm version 0.0.7 --no-git-tag-version',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.0.7',
    'git tag v0.0.7',
    'npm publish'
  ]);
});

test('release shell script skips the bump when already at the requested version', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);
  const repo = await createReleaseProject(t);

  const result = await execFileAsync(
    shellRunner,
    ['scripts/release.sh', '--version', '0.0.5'],
    { cwd: repo, env: fakeCommands.env, encoding: 'utf8' }
  );

  assert.match(result.stdout, /> echo package.json already at 0.0.5/);
  assert.doesNotMatch(result.stdout, /> npm version /);
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.0.5',
    'git tag v0.0.5',
    'npm publish'
  ]);
});

test('release shell script continues past a no-op commit on a clean tree', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, { commitNoop: true });
  const repo = await createReleaseProject(t);

  const result = await execFileAsync(
    shellRunner,
    ['scripts/release.sh', '--version', '0.0.5'],
    { cwd: repo, env: fakeCommands.env, encoding: 'utf8' }
  );

  assert.match(result.stdout, /> echo package.json already at 0.0.5/);
  assert.match(result.stdout, /nothing to commit, working tree clean/);
  assert.match(result.stdout, /> git tag v0.0.5/);
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.0.5',
    'git tag v0.0.5',
    'npm publish'
  ]);
});

test('release shell script still aborts when commit fails for a real reason', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, {
    failWhen: 'git commit -m chore(release): 0.0.5'
  });
  const repo = await createReleaseProject(t);

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', '--version', '0.0.5'], {
      cwd: repo,
      env: fakeCommands.env,
      encoding: 'utf8'
    })
  );

  const commands = await readCommands(fakeCommands.logPath);
  assert.ok(commands.includes('git commit -m chore(release): 0.0.5'));
  assert.ok(!commands.includes('git tag v0.0.5'));
  assert.ok(!commands.includes('npm publish'));
});

test('release shell script reuses an existing release tag at HEAD and continues to publish', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, { tagExists: true });
  const repo = await createReleaseProject(t);

  const result = await execFileAsync(
    shellRunner,
    ['scripts/release.sh', '--version', '0.0.5'],
    { cwd: repo, env: fakeCommands.env, encoding: 'utf8' }
  );

  assert.match(result.stdout, /> echo package.json already at 0.0.5/);
  assert.match(result.stdout, /tag v0\.0\.5 already exists at HEAD, continuing/);
  assert.deepEqual(await readCommands(fakeCommands.logPath), [
    'npm run source:refresh',
    'npm run test:all',
    'git add package.json package-lock.json template/.cowork-flow/.version',
    'git commit -m chore(release): 0.0.5',
    'npm publish'
  ]);
});

test('release shell script aborts when the release tag exists at a different commit', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t, { tagExists: true, tagMismatch: true });
  const repo = await createReleaseProject(t);

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', '--version', '0.0.5'], {
      cwd: repo,
      env: fakeCommands.env,
      encoding: 'utf8'
    })
  );

  const commands = await readCommands(fakeCommands.logPath);
  assert.ok(commands.includes('git commit -m chore(release): 0.0.5'));
  assert.ok(!commands.includes('npm publish'));
});

test('release shell script rejects a malformed --version before running anything', async (t) => {
  if (skipWithoutShell(t)) return;
  const fakeCommands = await createFakeCommands(t);
  const repo = await createReleaseProject(t);

  await assert.rejects(
    execFileAsync(shellRunner, ['scripts/release.sh', '--version', 'banana'], {
      cwd: repo,
      env: fakeCommands.env,
      encoding: 'utf8'
    })
  );

  assert.deepEqual(await readCommands(fakeCommands.logPath), []);
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
