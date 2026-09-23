import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { access, readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';
import { pluginManifest, readPluginMetadata } from '../src/lib/plugin-metadata.js';

const HOST_MANIFESTS = [
  ['codex', '.codex-plugin/plugin.json'],
  ['zcode', '.zcode-plugin/plugin.json'],
  ['qoder', '.qoder-plugin/plugin.json']
];
// Built from parts so this file can be scanned by the misspelling gate below.
const RETIRED_AUTHOR = ['fisk', 'likewater'].join('');
const SCAN_ROOTS = ['bin', 'presets', 'src', 'template'];
const SCAN_FILES = ['CHANGELOG.md', 'LICENSE', 'README.md', 'package.json'];

function manifestPath(host, relative) {
  return join(packageRoot, 'presets', host, ...relative.split('/'));
}

async function readManifest(host, relative) {
  return JSON.parse(await readFile(manifestPath(host, relative), 'utf8'));
}

// `git ls-files` sees only the index, so it returns nothing for a checkout
// without its own .git (an export nested inside another repository) and misses
// files that are not added yet. Either case would let this gate pass while
// scanning nothing, so the listing is trusted only when it actually covers the
// identity source; otherwise the shipped whitelist is walked instead.
const IDENTITY_SOURCE = 'presets/plugin-meta.json';

async function scanFiles() {
  try {
    const listed = execFileSync('git', ['ls-files'], { cwd: packageRoot, encoding: 'utf8' })
      .split('\n')
      .filter(Boolean);
    if (listed.includes(IDENTITY_SOURCE)) {
      return listed;
    }
  } catch {
    // No usable git listing; fall through to the whitelist walk.
  }
  const found = [];
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (['__pycache__', 'node_modules'].includes(entry.name)) {
          continue;
        }
        await walk(path);
      } else if (entry.isFile()) {
        found.push(path.slice(packageRoot.length + 1).replaceAll('\\', '/'));
      }
    }
  }
  for (const root of SCAN_ROOTS) {
    try {
      await access(join(packageRoot, root));
    } catch {
      continue;
    }
    await walk(join(packageRoot, root));
  }
  return [...found, ...SCAN_FILES];
}

test('host plugin manifests are exactly the metadata projection', async () => {
  const metadata = await readPluginMetadata();
  const { version } = await readPackageInfo();

  for (const [host, relative] of HOST_MANIFESTS) {
    const actual = await readFile(manifestPath(host, relative), 'utf8');
    const expected = `${JSON.stringify(pluginManifest(metadata, host, version), null, 2)}\n`;
    assert.equal(
      actual,
      expected,
      `${host} manifest must be the projection of presets/plugin-meta.json`
    );
  }
});

test('plugin identity is consistent across every shipped surface', async () => {
  const metadata = await readPluginMetadata();
  const packageInfo = await readPackageInfo();
  const license = await readFile(join(packageRoot, 'LICENSE'), 'utf8');

  assert.equal(packageInfo.author.name, metadata.author.name);
  assert.equal(packageInfo.author.email, metadata.author.email);
  assert.equal(packageInfo.homepage, `${metadata.repository}#readme`);
  assert.equal(packageInfo.repository.url, `git+${metadata.repository}.git`);
  assert.equal(packageInfo.bugs.url, `${metadata.repository}/issues`);
  assert.deepEqual(packageInfo.keywords, metadata.keywords);
  assert.match(license, new RegExp(`Copyright \\(c\\) \\d{4} ${metadata.author.name}\\b`));

  for (const [host, relative] of HOST_MANIFESTS) {
    const manifest = await readManifest(host, relative);
    assert.equal(manifest.author.name, metadata.author.name, `${host} manifest author`);
    assert.equal(manifest.license, metadata.license, `${host} manifest license`);
  }
});

test('the retired author misspelling appears nowhere in the shipped surface', async () => {
  const offenders = [];
  for (const relative of await scanFiles()) {
    let content;
    try {
      content = await readFile(join(packageRoot, ...relative.split('/')), 'utf8');
    } catch {
      continue;
    }
    if (content.includes(RETIRED_AUTHOR)) {
      offenders.push(relative);
    }
  }
  assert.deepEqual(offenders, [], `files still carrying ${RETIRED_AUTHOR}`);
});

test('codex manifest declares the interface block the host expects', async () => {
  const metadata = await readPluginMetadata();
  const manifest = await readManifest('codex', '.codex-plugin/plugin.json');

  assert.equal(manifest.interface.displayName, metadata.displayName);
  assert.equal(manifest.interface.developerName, metadata.author.name);
  assert.equal(manifest.interface.websiteURL, metadata.homepage);
  assert.equal(manifest.interface.category, metadata.category);
  assert.ok(manifest.interface.shortDescription.length > 0);
  assert.ok(manifest.interface.longDescription.length > manifest.interface.shortDescription.length);
});

test('qoder manifest carries the identity fields its schema supports', async () => {
  const metadata = await readPluginMetadata();
  const manifest = await readManifest('qoder', '.qoder-plugin/plugin.json');

  assert.equal(manifest.displayName, metadata.displayName);
  assert.equal(manifest.homepage, metadata.homepage);
  assert.equal(manifest.repository, metadata.repository);
  assert.deepEqual(manifest.keywords, metadata.keywords);
  // The qoder manifest schema has no icon field; adding one would be dead weight.
  assert.equal(manifest.icon, undefined);
  assert.equal(manifest.logo, undefined);
});

test('zcode manifest carries the fields zcode reads', async () => {
  const metadata = await readPluginMetadata();
  const manifest = await readManifest('zcode', '.zcode-plugin/plugin.json');

  assert.equal(manifest.author.name, metadata.author.name);
  assert.equal(manifest.author.url, metadata.author.url);
  assert.equal(manifest.homepage, metadata.homepage);
  // zcode's manifest display metadata maps author/authorUrl/homepage/version;
  // the display name comes from the marketplace listing, not the manifest.
  assert.equal(manifest.displayName, undefined);
  // The entry itself is asserted in test/zcode-plugin.test.js against this same
  // metadata field, which would follow any value; pin the slug zcode's listing
  // parser expects so a bogus category cannot pass both tests.
  assert.equal(metadata.marketplaceCategory, 'developer-tools');
});
