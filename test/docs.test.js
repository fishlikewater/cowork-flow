import assert from 'node:assert/strict';
import { access, readdir, readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';

// The documentation surface: everything a reader can land on from the package
// root or the repository front page.
const DOC_FILES = [
  'README.md',
  'CONTRIBUTING.md',
  'CHANGELOG.md',
  'docs/index.md',
  'docs/architecture.md',
  'docs/hosts.md',
  'docs/release.md'
];

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


test('the docs index links every document beside it', async () => {
  const index = await readDoc('docs/index.md');
  const linked = new Set(relativeTargets(index));

  const siblings = (await readdir(join(packageRoot, 'docs')))
    .filter((name) => name.endsWith('.md') && name !== 'index.md');

  assert.deepEqual(siblings.filter((name) => !linked.has(name)), []);
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
