import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { npmCommandOptions } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

test('npm package includes cli source and template assets', async (t) => {
  const npmCache = await mkdtemp(join(tmpdir(), 'cowork-flow-npm-cache-'));
  t.after(async () => {
    await rm(npmCache, { recursive: true, force: true });
  });

  const result = await execFileAsync('npm', ['pack', '--dry-run', '--json'], {
    cwd: packageRoot,
    encoding: 'utf8',
    ...npmCommandOptions(),
    env: {
      ...process.env,
      npm_config_cache: npmCache
    }
  });
  const [pack] = JSON.parse(result.stdout);
  const files = new Set(pack.files.map((file) => file.path));

  assert.equal(files.has('bin/cowork-flow.js'), true);
  assert.equal(files.has('src/cli.js'), true);
  assert.equal(files.has('template/AGENTS.md'), true);
  assert.equal(files.has('template/.cowork-flow/run'), true);
  assert.equal(files.has('template/.cowork-flow/run.cmd'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/run.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/change.py'), true);
  assert.equal(files.has('template/.codex/config.toml'), true);
  assert.equal(files.has('template/.codex/hooks.json'), true);
  assert.equal(files.has('template/.codex/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.agent/skills/start/SKILL.md'), true);
  assert.equal(files.has('template/.agent/skills/before-dev/SKILL.md'), true);
  assert.equal(files.has('template/.agent/skills/check/SKILL.md'), true);
  assert.equal(files.has('template/.agent/skills/continue/SKILL.md'), true);
  assert.equal(files.has('template/.agent/skills/meta/SKILL.md'), true);
  assert.equal(files.has('template/.agent/skills/python-design/SKILL.md'), true);
  assert.equal([...files].some((file) => file.startsWith('template/.superpowers/')), false);
  assert.equal(
    [...files].some((file) => file.includes('__pycache__') || file.endsWith('.pyc')),
    false
  );
});

test('package metadata exposes release script and synchronized lockfile version', async () => {
  const packageInfo = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  const packageLock = JSON.parse(await readFile(join(packageRoot, 'package-lock.json'), 'utf8'));

  assert.equal(packageInfo.scripts.release, 'sh scripts/release.sh');
  assert.equal(packageLock.version, packageInfo.version);
  assert.equal(packageLock.packages[''].version, packageInfo.version);
});
