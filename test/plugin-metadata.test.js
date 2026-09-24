import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { access, readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';
import zlib from 'node:zlib';

import { readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';
import { marketplaceIconUrl, pluginManifest, readPluginMetadata } from '../src/lib/plugin-metadata.js';

const HOST_MANIFESTS = [
  ['claude-code', '.claude-plugin/plugin.json'],
  ['codex', '.codex-plugin/plugin.json'],
  ['zcode', '.zcode-plugin/plugin.json'],
  ['qoder', '.qoder-plugin/plugin.json']
];
// Which hosts actually read an icon, and under which key. codex takes a
// payload-relative path plus a brand colour; zcode reads its icon from the
// marketplace entry, never from the manifest; qoder's manifest schema has no
// icon field at all, so writing one would be a key the host never reads, and
// claude-code's skills-directory manifest schema has none either.
const HOST_ICON_KEYS = {
  'claude-code': [],
  codex: ['brandColor', 'logo'],
  zcode: [],
  qoder: []
};
const ICON_KEY_PATTERN = /^(brandColor|brandColorDark|composerIcon|heroImage|icon|icons|logo|logoDark|screenshots)$/;
// Built from parts so this file can be scanned by the misspelling gate below.
const RETIRED_AUTHOR = ['fisk', 'likewater'].join('');
// The docs are a shipped surface too (package.json `files`), so the retired
// spelling has to stay out of them and not only out of the code.
const SCAN_ROOTS = ['bin', 'docs', 'presets', 'src', 'template'];
const SCAN_FILES = ['CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', 'README.md', 'package.json'];

function manifestPath(host, relative) {
  return join(packageRoot, 'presets', host, ...relative.split('/'));
}

// No PNG library here on purpose, and decoding by hand is the only way to gate
// this asset at all: re-rendering the SVG would need a browser, which a test
// cannot assume. Without the decode, "the raster is a stale or wrong image"
// passes every structural check — an all-red 512x512 replacement is a valid
// 512x512 PNG. The assertions below are the ones that make the shipped bytes the
// mark: RGBA, a transparent background, a mark that does not bleed to the edges,
// and the brand colour as its dominant solid colour.
function decodePng(buffer) {
  assert.ok(
    buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])),
    'assets/icon.png is not a PNG'
  );
  assert.equal(buffer.subarray(12, 16).toString('latin1'), 'IHDR');
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  const bitDepth = buffer[24];
  const colourType = buffer[25];
  const channels = { 0: 1, 2: 3, 4: 2, 6: 4 }[colourType];
  assert.ok(channels, `unsupported PNG colour type: ${colourType}`);
  assert.equal(bitDepth, 8, 'only 8-bit channels are expected for this asset');

  const parts = [];
  for (let offset = 8; offset + 12 <= buffer.length;) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString('latin1');
    if (type === 'IDAT') {
      parts.push(buffer.subarray(offset + 8, offset + 8 + length));
    }
    if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  const raw = zlib.inflateSync(Buffer.concat(parts));

  const stride = width * channels;
  const pixels = Buffer.alloc(height * stride);
  for (let y = 0, cursor = 0; y < height; y += 1) {
    const filter = raw[cursor];
    cursor += 1;
    const line = raw.subarray(cursor, cursor + stride);
    cursor += stride;
    const row = pixels.subarray(y * stride, (y + 1) * stride);
    const prior = y === 0 ? null : pixels.subarray((y - 1) * stride, y * stride);
    for (let x = 0; x < stride; x += 1) {
      const left = x >= channels ? row[x - channels] : 0;
      const above = prior === null ? 0 : prior[x];
      const upperLeft = prior === null || x < channels ? 0 : prior[x - channels];
      let value = line[x];
      if (filter === 1) {
        value += left;
      } else if (filter === 2) {
        value += above;
      } else if (filter === 3) {
        value += (left + above) >> 1;
      } else if (filter === 4) {
        const p = left + above - upperLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - above);
        const pc = Math.abs(p - upperLeft);
        value += pa <= pb && pa <= pc ? left : pb <= pc ? above : upperLeft;
      }
      row[x] = value & 0xff;
    }
  }
  return { width, height, channels, pixels };
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
  assert.equal(manifest.interface.logo, './assets/logo.svg');
  assert.equal(manifest.interface.brandColor, metadata.brandColor);
  // codex resolves the path against the plugin root and the payload is copied
  // into $CODEX_HOME on its own, so the file has to sit inside the payload.
  await access(join(packageRoot, 'presets', 'codex', ...manifest.interface.logo.replace('./', '').split('/')));
});

test('the brand mark has one source and two derivations', async () => {
  const metadata = await readPluginMetadata();
  const source = await readFile(join(packageRoot, ...metadata.icon.source.split('/')), 'utf8');
  const coloured = source.split('currentColor').join(metadata.brandColor);

  // The source stays colourless on purpose: the brand colour lives in
  // plugin-meta.json only, and both derivations bake it in from there.
  assert.notEqual(coloured, source, 'assets/icon.svg must not hardcode the brand colour');
  assert.match(coloured, new RegExp(metadata.brandColor), 'the source must be recolourable');

  const payloadCopy = await readFile(
    join(packageRoot, 'presets', 'codex', 'assets', 'logo.svg'),
    'utf8'
  );
  assert.equal(
    payloadCopy,
    coloured,
    'the codex payload copy must be assets/icon.svg with brandColor substituted'
  );
});

test('the shipped raster is the mark, not just any 512x512 PNG', async () => {
  const metadata = await readPluginMetadata();
  const image = decodePng(await readFile(join(packageRoot, ...metadata.icon.raster.split('/'))));

  assert.deepEqual({ width: image.width, height: image.height }, { width: 512, height: 512 });
  assert.equal(image.channels, 4, 'the mark must carry an alpha channel, not sit on a white plate');

  const solid = new Map();
  let transparent = 0;
  let minX = image.width;
  let minY = image.height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < image.height; y += 1) {
    for (let x = 0; x < image.width; x += 1) {
      const at = (y * image.width + x) * 4;
      const alpha = image.pixels[at + 3];
      if (alpha === 0) {
        transparent += 1;
      } else {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
      if (alpha === 255) {
        const hex = `#${[0, 1, 2].map((offset) => image.pixels[at + offset].toString(16).padStart(2, '0')).join('')}`;
        solid.set(hex, (solid.get(hex) ?? 0) + 1);
      }
    }
  }

  assert.ok(transparent > 0, 'the mark must sit on transparency');
  assert.ok(solid.size > 0, 'the mark must have fully opaque pixels');
  // A full-bleed image is a plate, not a mark: the 24-grid keeps its own padding,
  // so the drawn area has to stay strictly inside the canvas.
  assert.ok(
    minX > 0 && minY > 0 && maxX < image.width - 1 && maxY < image.height - 1,
    `the mark must not bleed to the canvas edge, got ${minX},${minY},${maxX},${maxY}`
  );
  const dominant = [...solid.entries()].sort((a, b) => b[1] - a[1])[0][0];
  assert.equal(
    dominant.toUpperCase(),
    metadata.brandColor.toUpperCase(),
    'the solid colour of the mark must be the brand colour, not some other export'
  );
});

// The byte-equality gate above compares each manifest with its projection, so it
// cannot see this: add an unsupported key to the projection, regenerate the
// manifest, and byte-equality is still satisfied. This is the gate that catches
// "we taught the projection to write a key this host never reads".
test('each host manifest carries exactly the icon keys its schema supports', async () => {
  for (const [host, relative] of HOST_MANIFESTS) {
    const manifest = await readManifest(host, relative);
    const declared = new Set();
    const visit = (node) => {
      if (node === null || typeof node !== 'object') {
        return;
      }
      for (const [key, value] of Object.entries(node)) {
        if (ICON_KEY_PATTERN.test(key)) {
          declared.add(key);
        }
        visit(value);
      }
    };
    visit(manifest);
    assert.deepEqual(
      [...declared].sort(),
      [...HOST_ICON_KEYS[host]].sort(),
      `${host} manifest icon keys must match what the host actually reads`
    );
  }
});

test('the zcode marketplace icon URL is an absolute https URL pointing at the shipped raster', async () => {
  const metadata = await readPluginMetadata();
  const url = marketplaceIconUrl(metadata);

  // zcode keeps an icon only when `icon.startsWith('https://')` and drops
  // anything else without a warning, so a relative path would fail silently.
  assert.ok(url.startsWith('https://'), `zcode drops a non-https icon: ${url}`);
  assert.equal(
    url,
    'https://raw.githubusercontent.com/'
      + `${metadata.repository.replace('https://github.com/', '')}/`
      + `${metadata.defaultBranch}/${metadata.icon.raster}`
  );
  // The tail is the repo-relative path, so the URL can only 404 because the
  // branch lacks the file — never because the URL and the file drifted apart.
  await access(join(packageRoot, ...metadata.icon.raster.split('/')));
});

test('the icon URL derivation refuses metadata it cannot turn into a public URL', () => {
  const base = { repository: 'https://github.com/x/y', defaultBranch: 'dev', icon: { raster: 'a.png' } };

  assert.throws(() => marketplaceIconUrl({ ...base, repository: 'https://gitlab.com/x/y' }), /GitHub/);
  assert.throws(() => marketplaceIconUrl({ ...base, defaultBranch: '' }), /defaultBranch/);
  assert.throws(() => marketplaceIconUrl({ ...base, icon: {} }), /icon\.raster/);
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

test('claude-code manifest declares the skills directory and nothing it cannot read', async () => {
  const metadata = await readPluginMetadata();
  const manifest = await readManifest('claude-code', '.claude-plugin/plugin.json');

  assert.equal(manifest.displayName, metadata.displayName);
  assert.equal(manifest.repository, metadata.repository);
  assert.deepEqual(manifest.keywords, metadata.keywords);
  // The whole point of this plugin channel: the folder is a plugin because it
  // carries this manifest, and `skills` is what Claude Code then loads.
  assert.equal(manifest.skills, './skills/');
  // No icon key exists in this schema, and no hooks/agents either: the project
  // delivers injection and the fixed subagents from its own .claude/ tree.
  for (const key of ['icon', 'logo', 'hooks', 'agents']) {
    assert.equal(manifest[key], undefined, `claude-code manifest must not declare ${key}`);
  }
  await access(join(packageRoot, 'presets', 'claude-code', 'skills', 'cowork-flow-bootstrap', 'SKILL.md'));
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
