import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { access, mkdir, mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { npmCommandOptions, readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

function runNpm(args, options = {}) {
  return execFileAsync('npm', args, {
    cwd: packageRoot,
    encoding: 'utf8',
    ...npmCommandOptions(),
    ...options
  });
}

test('a packed tarball installs and runs the published CLI', async (t) => {
  const workspace = await mkdtemp(join(tmpdir(), 'cowork-flow-tarball-'));
  t.after(async () => {
    await rm(workspace, { recursive: true, force: true });
  });

  const packDirectory = join(workspace, 'pack');
  const project = join(workspace, 'project');
  const cache = join(workspace, 'npm-cache');
  await mkdir(packDirectory, { recursive: true });
  await mkdir(project, { recursive: true });
  await mkdir(cache, { recursive: true });

  const packResult = await runNpm(['pack', '--json', '--pack-destination', packDirectory], {
    env: { ...process.env, npm_config_cache: cache }
  });
  const [pack] = JSON.parse(packResult.stdout);
  assert.ok(pack?.filename, 'npm pack must report the generated tarball');
  const tarball = join(packDirectory, pack.filename);
  await access(tarball);

  await runNpm([
    'install',
    tarball,
    '--prefix',
    project,
    '--ignore-scripts',
    '--no-audit',
    '--no-fund',
    '--prefer-offline'
  ], {
    env: { ...process.env, npm_config_cache: cache }
  });

  const installedRoot = join(project, 'node_modules', 'cowork-flow');
  const installedEntry = join(installedRoot, 'bin', 'cowork-flow.js');
  await access(installedEntry);
  const { version } = await readPackageInfo();
  const versionResult = await execFileAsync(process.execPath, [installedEntry, '--version'], {
    cwd: project,
    encoding: 'utf8'
  });
  assert.equal(versionResult.stdout.trim(), version);

  const target = join(workspace, 'initialized-project');
  const initResult = await execFileAsync(process.execPath, [
    installedEntry,
    'project',
    'init',
    target,
    '--developer',
    'tarball-smoke',
    '--platform',
    'codex'
  ], {
    cwd: project,
    encoding: 'utf8'
  });
  assert.match(initResult.stdout, /Developer initialized: tarball-smoke/);
  await access(join(target, '.cowork-flow', 'run.cmd'));
  await access(join(target, '.codex', 'config.toml'));
});
