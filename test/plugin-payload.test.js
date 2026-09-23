import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';
import { pluginPayload, stampPayloadManifest } from '../src/lib/plugin-payload.js';

const DEMO_MANIFEST = '.demo-plugin/plugin.json';


async function tempDir(t) {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-payload-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}


test('pluginPayload resolves the declared source and manifest', () => {
  assert.deepEqual(pluginPayload('zcode'), {
    sourceDir: join(packageRoot, 'presets', 'zcode'),
    manifest: '.zcode-plugin/plugin.json'
  });
  // opencode ships no machine-level plugin payload, so an install command for it
  // would have nothing to copy; the accessor refuses instead of returning null
  // and pushing the failure into a later copy.
  assert.throws(
    () => pluginPayload('opencode'),
    /declares no plugin payload manifest/
  );
});


test('stampPayloadManifest rewrites the version and nothing else', async (t) => {
  const dir = await tempDir(t);
  await mkdir(join(dir, '.demo-plugin'), { recursive: true });
  const original = {
    name: 'cowork-flow',
    version: '0.0.1',
    description: '中文描述',
    author: { name: 'fishlikewater' }
  };
  await writeFile(
    join(dir, DEMO_MANIFEST),
    `${JSON.stringify(original, null, 2)}\n`,
    'utf8'
  );

  const stamped = await stampPayloadManifest(dir, DEMO_MANIFEST, '9.9.9');

  const text = await readFile(stamped, 'utf8');
  // Byte shape must match scripts/release.sh's stamping: a release stamps the
  // source manifest and an install stamps the payload, so the two files have to
  // stay comparable.
  assert.equal(
    text,
    `${JSON.stringify({ ...original, version: '9.9.9' }, null, 2)}\n`
  );
  assert.deepEqual(
    Object.keys(JSON.parse(text)),
    Object.keys(original),
    'key order must survive the stamp'
  );
  assert.deepEqual(
    await readdir(join(dir, '.demo-plugin')),
    ['plugin.json'],
    'the temporary file must not survive the rename'
  );
});


test('stampPayloadManifest refuses a payload without a readable manifest', async (t) => {
  const dir = await tempDir(t);

  await assert.rejects(
    () => stampPayloadManifest(dir, DEMO_MANIFEST, '9.9.9'),
    /Plugin payload manifest missing or unreadable/
  );
});


test('every plugin installer stamps its payload through the shared helper', async () => {
  // Without this the three "installed version equals the package version"
  // assertions stay green even if stamping is dropped: the shipped source
  // manifests already carry the release version.
  for (const host of ['codex', 'zcode', 'qoder']) {
    const installer = await readFile(
      join(packageRoot, 'src', 'commands', `install-${host}-plugin.js`),
      'utf8'
    );
    assert.match(
      installer,
      /stampPayloadManifest\(/,
      `install-${host}-plugin.js must stamp the installed payload`
    );
  }
});
