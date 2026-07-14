import assert from 'node:assert/strict';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { test } from 'node:test';

import { runInstallZCodePlugin } from '../src/commands/install-zcode-plugin.js';
import { readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot, templateRoot } from '../src/lib/paths.js';

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

async function assertTreesEqual(expectedRoot, actualRoot) {
  const expectedFiles = await listRelativeFiles(expectedRoot);
  const actualFiles = await listRelativeFiles(actualRoot);
  assert.deepEqual(actualFiles, expectedFiles);

  for (const file of expectedFiles) {
    const expected = await readFile(join(expectedRoot, file), 'utf8');
    const actual = await readFile(join(actualRoot, file), 'utf8');
    assert.equal(actual, expected, file);
  }
}

test('zcode scaffold source does not commit standalone spec tree', async () => {
  await assert.rejects(
    access(join(templateRoot, '.zcode', 'scaffold', '.cowork-flow', 'spec'))
  );
});

test('install-zcode-plugin materializes scaffold spec from canonical template', async (t) => {
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

  await assertTreesEqual(join(packageRoot, 'template', '.cowork-flow', 'spec'), installedSpec);
});
