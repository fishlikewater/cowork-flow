import assert from 'node:assert/strict';
import { access, readdir, readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';
import { loadHostAssetManifest } from '../src/lib/host-assets.js';

// The documentation surface: everything a reader can land on from the package
// root or the repository front page.
const DOC_FILES = [
  'README.md',
  'README.en.md',
  'CONTRIBUTING.md',
  'SECURITY.md',
  'CHANGELOG.md',
  'docs/index.md',
  'docs/index.en.md',
  'docs/architecture.md',
  'docs/architecture.en.md',
  'docs/hosts.md',
  'docs/hosts.en.md',
  'docs/release.md',
  'docs/release.en.md',
  'docs/direction.md',
  'docs/direction.en.md'
];

const DOCS_DIR = 'docs';
const ENGLISH_SUFFIX = '.en.md';

// Headings the README used to carry before the detail moved into docs/. They
// must not creep back: a second copy of the same facts is what drifts. Stored
// without their level so a demoted or promoted copy is caught too.
const MIGRATED_HEADINGS = [
  '一句话',
  '当前能力',
  '阅读导航',
  '仓库结构',
  '架构与扩展点',
  'Skills 分发机制',
  '宿主与机器级组件',
  'dev refresh 行为',
  'MCP 客户端接入',
  'ZCode 插件',
  'DSH 接入',
  'DSH 预设',
  'Kimi Code hook',
  'Qoder（插件形态）',
  'Codex（插件形态）',
  '常用命令',
  '支持与故障诊断',
  'Party Mode',
  '发布',
  '接入原则'
];

// npm always publishes these regardless of `files`, so a README link to one of
// them resolves on the registry page without being declared.
const ALWAYS_SHIPPED = ['README.md', 'LICENSE', 'package.json'];


async function readDoc(relativePath) {
  return readFile(join(packageRoot, ...relativePath.split('/')), 'utf8');
}


// Links inside fenced blocks are samples, not links.
function stripFences(markdown) {
  const kept = [];
  let fenced = false;
  for (const line of markdown.split('\n')) {
    if (line.trimStart().startsWith('```')) {
      fenced = !fenced;
      continue;
    }
    if (!fenced) {
      kept.push(line);
    }
  }
  return kept.join('\n');
}


function relativeTargets(markdown) {
  const body = stripFences(markdown);
  const targets = [];
  const inline = /\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+"[^"]*")?\)/g;
  for (const match of [...body.matchAll(inline), ...body.matchAll(/^\[[^\]]+\]:\s*(\S+)/gm)]) {
    const target = match[1];
    if (/^[a-z][a-z0-9+.-]*:/i.test(target) || target.startsWith('#') || target.startsWith('/')) {
      continue;
    }
    targets.push(target.split('#')[0]);
  }
  return targets;
}


function isEnglishDoc(name) {
  return name.endsWith(ENGLISH_SUFFIX);
}


function chinesePeer(name) {
  return isEnglishDoc(name)
    ? name.slice(0, -ENGLISH_SUFFIX.length) + '.md'
    : name;
}


function englishPeer(name) {
  return isEnglishDoc(name) ? name : name.slice(0, -'.md'.length) + ENGLISH_SUFFIX;
}


function setDifference(left, right) {
  return [...left].filter((name) => !right.has(name)).sort();
}


function readmeHostNames(text, language) {
  const pattern = language === 'en' ? /^Supports (.+)\.$/m : /^支持 (.+)。$/m;
  const match = text.match(pattern);
  assert.ok(match, `missing ${language} host support line`);
  const parts = language === 'en'
    ? match[1].replace(/,\s*and\s+/i, ', ').split(',')
    : match[1].replace(/\s+和\s+/g, '、').split('、');
  return new Set(parts.map((part) => part.trim()).filter(Boolean));
}


function documentedHostNames(text, manifestNames) {
  return new Set(
    text
      .split('\n')
      .filter((line) => line.startsWith('## '))
      .map((line) => line.slice(3).trim())
      .filter((name) => manifestNames.has(name))
  );
}


async function docsSiblings() {
  return (await readdir(join(packageRoot, DOCS_DIR))).filter((name) => name.endsWith('.md'));
}


// The Chinese page is the source of truth and the English page its translation.
// Comparing heading levels keeps the English page from silently dropping,
// merging, or inventing sections while leaving the wording free to differ.
function headingLevels(markdown) {
  return headings(markdown).map((heading) => heading.level);
}


function headings(markdown) {
  return stripFences(markdown)
    .split('\n')
    .filter((line) => /^#{1,6}\s/.test(line))
    .map((line) => ({
      level: line.match(/^#+/)[0].length,
      text: line.replace(/^#+\s*/, '').trim()
    }));
}


test('every documentation file exists', async () => {
  for (const relativePath of DOC_FILES) {
    await access(join(packageRoot, ...relativePath.split('/')));
  }
});


test('every relative link in the documentation resolves', async () => {
  const broken = [];

  for (const relativePath of DOC_FILES) {
    const from = dirname(join(packageRoot, ...relativePath.split('/')));
    for (const target of relativeTargets(await readDoc(relativePath))) {
      if (target.length === 0) {
        continue;
      }
      try {
        await access(resolve(from, target));
      } catch {
        broken.push(`${relativePath} -> ${target}`);
      }
    }
  }

  assert.deepEqual(broken, [], 'documentation links must point at files that exist');
});


// Each language has its own index: a Chinese reader stays in the Chinese set,
// an English reader in the English set. A page missing from its index is
// effectively invisible from that entry point.
test('each documentation index links every document of its own language', async () => {
  const files = await docsSiblings();
  const chinese = files.filter((name) => !isEnglishDoc(name) && name !== 'index.md');
  const english = files.filter((name) => isEnglishDoc(name) && name !== 'index.en.md');

  const chineseLinked = new Set(relativeTargets(await readDoc('docs/index.md')));
  const englishLinked = new Set(relativeTargets(await readDoc('docs/index.en.md')));

  assert.deepEqual(chinese.filter((name) => !chineseLinked.has(name)), []);
  assert.deepEqual(english.filter((name) => !englishLinked.has(name)), []);
});


// Translation drift starts with a page that exists in one language only: the
// reader switches language and lands on a missing file. Every docs/ page must
// have its counterpart.
test('every documentation page has a counterpart in the other language', async () => {
  const names = new Set(await docsSiblings());
  const missing = [];

  for (const name of names) {
    const peer = isEnglishDoc(name) ? chinesePeer(name) : englishPeer(name);
    if (!names.has(peer)) {
      missing.push(`${name} -> ${peer}`);
    }
  }

  assert.deepEqual(missing, [], 'every docs page needs a peer in the other language');
});


// The English page is a translation of the Chinese source: the section
// structure must match exactly (headings may be translated, not added, merged,
// or dropped), and no heading may be left in Chinese.
test('English documentation mirrors the Chinese heading structure', async () => {
  const names = await docsSiblings();
  const english = names.filter(isEnglishDoc);

  assert.ok(english.length > 0, 'the docs surface must keep its English pages');

  for (const name of english) {
    const source = chinesePeer(name);
    assert.deepEqual(
      headingLevels(await readDoc(`${DOCS_DIR}/${name}`)),
      headingLevels(await readDoc(`${DOCS_DIR}/${source}`)),
      `${name} must keep the section structure of ${source}`
    );

    for (const heading of headings(await readDoc(`${DOCS_DIR}/${name}`))) {
      assert.doesNotMatch(
        heading.text,
        /\p{Script=Han}/u,
        `${name} has an untranslated heading: ${heading.text}`
      );
    }
  }
});


// The language switch is the way in for a reader who lands on either version;
// it must exist in both directions or the pairing stays invisible.
test('each documentation page links its counterpart language', async () => {
  for (const name of await docsSiblings()) {
    const peer = isEnglishDoc(name) ? chinesePeer(name) : englishPeer(name);
    const linked = new Set(relativeTargets(await readDoc(`${DOCS_DIR}/${name}`)));
    assert.ok(linked.has(peer), `${name} must link its counterpart ${peer}`);
  }
});


// The English README is the entry point for an English reader. If a link target
// has an English counterpart, the reader must land on the English page rather
// than being sent back to the Chinese source.
test('README.en.md links English pages when a counterpart exists', async () => {
  const misplaced = [];

  for (const target of relativeTargets(await readDoc('README.en.md'))) {
    if (!target.startsWith(`${DOCS_DIR}/`) || !target.endsWith('.md') || isEnglishDoc(target)) {
      continue;
    }
    const english = englishPeer(target);
    try {
      await access(join(packageRoot, ...english.split('/')));
    } catch {
      continue;
    }
    misplaced.push(`${target} -> ${english}`);
  }

  assert.deepEqual(misplaced, [], 'README.en.md must link the English docs');
});


test('README carries no heading that was migrated into docs/', async () => {
  const headings = new Set(
    (await readDoc('README.md'))
      .split('\n')
      .filter((line) => line.startsWith('#'))
      .map((line) => line.replace(/^#+\s*/, '').trim())
  );

  assert.deepEqual(
    MIGRATED_HEADINGS.filter((heading) => headings.has(heading)),
    []
  );
});


// The README is the front page of a CLI package, so its links are what a reader
// follows from npm; every root-level document it points at has to ship. The
// list is derived from the README rather than restated, so adding a document
// without shipping it fails here.
test('the npm package ships every root document the README links to', async () => {
  const packageInfo = JSON.parse(await readDoc('package.json'));
  const shipped = new Set([...packageInfo.files, ...ALWAYS_SHIPPED]);

  const rootDocs = relativeTargets(await readDoc('README.md')).filter(
    (target) => target.length > 0 && !target.includes('/')
  );
  assert.ok(rootDocs.length > 0, 'the README must still link its root documents');

  assert.deepEqual(rootDocs.filter((target) => !shipped.has(target)), []);
});


test('every manifest host appears in README and hosts docs', async () => {
  const manifestNames = new Set(
    loadHostAssetManifest().platforms.map((platform) => platform.displayName)
  );
  assert.ok(manifestNames.size > 0, 'the host manifest must declare platforms');

  for (const [path, language] of [['README.md', 'zh'], ['README.en.md', 'en']]) {
    const documented = readmeHostNames(await readDoc(path), language);
    assert.deepEqual(
      setDifference(documented, manifestNames),
      [],
      `${path} lists hosts the manifest does not declare`
    );
    assert.deepEqual(
      setDifference(manifestNames, documented),
      [],
      `${path} is missing manifest hosts`
    );
  }

  for (const path of ['docs/hosts.md', 'docs/hosts.en.md']) {
    const documented = documentedHostNames(await readDoc(path), manifestNames);
    assert.deepEqual(
      setDifference(manifestNames, documented),
      [],
      `${path} is missing manifest hosts`
    );
  }
});


test('host docs describe the single install-state read model', async () => {
  const cases = [
    ['docs/hosts.md', ['cwf host inspect', 'HOST-INSPECT-UNAVAILABLE', 'host-install-inspection.md']],
    ['docs/hosts.en.md', ['cwf host inspect', 'HOST-INSPECT-UNAVAILABLE', 'host-install-inspection.md']],
    ['docs/architecture.md', ['HOST-INSPECT-UNAVAILABLE', 'host-install-inspection.md']],
    ['docs/architecture.en.md', ['HOST-INSPECT-UNAVAILABLE', 'host-install-inspection.md']]
  ];
  for (const [path, needles] of cases) {
    const text = await readDoc(path);
    for (const needle of needles) {
      assert.ok(text.includes(needle), `${path} must mention ${needle}`);
    }
  }
});


test('CHANGELOG follows Keep a Changelog', async () => {
  const changelog = await readDoc('CHANGELOG.md');

  // One newline at EOF: a trailing blank line shows up as a diff in every
  // release commit.
  assert.ok(changelog.endsWith('\n') && !changelog.endsWith('\n\n'));

  const lines = changelog.split('\n');
  const headings = lines.filter((line) => line.startsWith('## '));
  assert.equal(headings[0], '## [Unreleased]');

  const versions = [];
  for (const heading of headings) {
    const bracketed = heading.match(/^## \[([^\]]+)\](?: - (\d{4}-\d{2}-\d{2}))?$/);
    assert.ok(bracketed, `CHANGELOG heading is not bracketed: ${heading}`);
    if (bracketed[1] !== 'Unreleased') {
      assert.ok(bracketed[2], `released version needs a date: ${heading}`);
      versions.push(bracketed[1]);
    }
  }
  assert.ok(versions.length > 0, 'the changelog must keep its released history');

  // Without the link definition the bracketed headings render as literal
  // brackets instead of linking to the diff.
  for (const name of ['Unreleased', ...versions]) {
    assert.match(
      changelog,
      new RegExp(`^\\[${name.replaceAll('.', '\\.')}\\]: https://`, 'm'),
      `CHANGELOG is missing the link definition for ${name}`
    );
  }

  // Keep a Changelog only defines these categories; a descriptive sub-heading
  // belongs one level down, as `####`.
  const start = lines.indexOf('## [Unreleased]');
  const end = lines.findIndex((line, index) => index > start && line.startsWith('## ['));
  const categories = lines
    .slice(start, end)
    .filter((line) => line.startsWith('### '))
    .map((line) => line.slice(4));
  const allowed = new Set(['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Security']);
  assert.deepEqual(categories.filter((name) => !allowed.has(name)), []);
  assert.ok(categories.length > 0, 'Unreleased must classify its changes');
});
