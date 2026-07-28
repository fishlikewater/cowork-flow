import assert from 'node:assert/strict';
import { access, cp, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { test } from 'node:test';

import { runInstallZCodePlugin } from '../src/commands/install-zcode-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { templateRoot } from '../src/lib/paths.js';

async function listRelativeFiles(root) {
  const { readdir } = await import('node:fs/promises');
  const result = [];

  async function walk(dir) {
    const entries = await readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(path);
      } else if (entry.isFile()) {
        result.push(relative(root, path).replaceAll('\\', '/'));
      }
    }
  }

  await walk(root);
  return result.sort();
}

test('zcode scaffold source does not commit standalone spec tree', async () => {
  await assert.rejects(
    access(join(templateRoot, '.zcode', 'scaffold', '.cowork-flow', 'spec'))
  );
});

test('install-zcode-plugin keeps workflow files out of zcode scaffold', async (t) => {
  const zcodeHome = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-home-'));
  const originalZCodeHome = process.env.ZCODE_HOME;
  process.env.ZCODE_HOME = zcodeHome;
  t.after(async () => {
    if (originalZCodeHome === undefined) {
      delete process.env.ZCODE_HOME;
    } else {
      process.env.ZCODE_HOME = originalZCodeHome;
    }
    await rm(zcodeHome, { recursive: true, force: true });
  });

  await runInstallZCodePlugin(['--force']);

  const { version } = await readPackageInfo();
  const installedSpec = join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version,
    'scaffold',
    '.cowork-flow',
    'spec'
  );

  await assert.rejects(access(installedSpec));

  const installedScaffold = join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version,
    'scaffold'
  );
  const scaffoldFiles = await listRelativeFiles(installedScaffold);
  assert.equal(
    scaffoldFiles.some((file) => file === '.cowork-flow' || file.startsWith('.cowork-flow/')),
    false
  );
  await access(join(installedScaffold, 'AGENTS.md'));
  await access(join(installedScaffold, 'CLAUDE.md'));
  await access(join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version,
    'hooks',
    'inject-context.js'
  ));
  await access(join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version,
    'skills',
    'cowork-flow',
    'SKILL.md'
  ));
});

test('zcode scaffold cannot create workflow files in module directories', async (t) => {
  const zcodeHome = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-home-'));
  const projectRoot = await mkdtemp(join(tmpdir(), 'cowork-flow-zcode-project-'));
  const originalZCodeHome = process.env.ZCODE_HOME;
  process.env.ZCODE_HOME = zcodeHome;
  t.after(async () => {
    if (originalZCodeHome === undefined) {
      delete process.env.ZCODE_HOME;
    } else {
      process.env.ZCODE_HOME = originalZCodeHome;
    }
    await rm(zcodeHome, { recursive: true, force: true });
    await rm(projectRoot, { recursive: true, force: true });
  });

  await runInstallZCodePlugin(['--force']);

  const { version } = await readPackageInfo();
  const installedScaffold = join(
    zcodeHome,
    'cli',
    'plugins',
    'cache',
    'zcode-plugins-official',
    'cowork-flow',
    version,
    'scaffold'
  );
  const moduleA = join(projectRoot, 'module-a');
  const moduleB = join(projectRoot, 'apps', 'module-b');
  await mkdir(moduleA, { recursive: true });
  await mkdir(moduleB, { recursive: true });

  for (const target of [projectRoot, moduleA, moduleB]) {
    await cp(installedScaffold, target, { recursive: true, force: true });
  }

  await assert.rejects(access(join(projectRoot, '.cowork-flow')));
  await assert.rejects(access(join(moduleA, '.cowork-flow')));
  await assert.rejects(access(join(moduleB, '.cowork-flow')));
});
