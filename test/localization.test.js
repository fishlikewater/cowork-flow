import assert from 'node:assert/strict';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';

import { main } from '../src/cli.js';
import {
  createHostRegistry,
  hostRegistry,
  loadHostAssetManifest
} from '../src/lib/host-assets.js';
import {
  DEFAULT_LANGUAGE,
  normalizeLanguage,
  parseLanguage,
  readLanguageSetting,
  readProjectLanguage,
  readProjectLanguageStrict,
  withLanguage
} from '../src/lib/language.js';
import { templateRoot } from '../src/lib/paths.js';
import { createTempDir, exists, readText } from './helpers/fs.js';

const ANCHOR = '.cowork-flow/spec/contracts/decision-anchor.md';
const PLAN_TEMPLATE = '.cowork-flow/templates/plan-template.md';
const LANGUAGE_FIXTURES = new URL('../tests/fixtures/language-config/', import.meta.url);

function createIo() {
  return {
    stdout: '',
    stderr: '',
    writeOut(message) {
      this.stdout += message;
    },
    writeErr(message) {
      this.stderr += message;
    }
  };
}

function baseAsset(relativePath) {
  return join(templateRoot, ...relativePath.split('/'));
}

function localizedAsset(relativePath, language = 'en-US') {
  return join(templateRoot, 'locales', language, ...relativePath.split('/'));
}

async function initProject(target, language, io = createIo()) {
  const args = ['init', target, '--developer', 'codex', '--host', 'codex'];
  if (language) {
    args.push('--language', language);
  }
  const code = await main(args, { io, prompt: null });
  assert.equal(code, 0, io.stderr);
  return io;
}

test('language aliases normalize to the supported canonical values', () => {
  assert.equal(normalizeLanguage('zh'), 'zh-CN');
  assert.equal(normalizeLanguage('ZH_CN'), 'zh-CN');
  assert.equal(normalizeLanguage('en'), 'en-US');
  assert.equal(normalizeLanguage('EN-us'), 'en-US');
  assert.equal(normalizeLanguage('fr'), null);
  assert.equal(normalizeLanguage(undefined), null);
});

test('language parsing accepts quotes and whitespace-separated comments only', () => {
  assert.equal(parseLanguage('language: en-US\n'), 'en-US');
  assert.equal(parseLanguage('language: "en-US"\r\n'), 'en-US');
  assert.equal(parseLanguage('language: "en"  # note\n'), 'en-US');
  assert.equal(parseLanguage("language: 'zh_CN'\n"), 'zh-CN');
  assert.equal(parseLanguage('codex:\n  language: en-US\n'), null);
  assert.equal(parseLanguage('language: "en-US"#not-a-comment\n'), null);
});

test('node reader matches the shared language fixtures', async () => {
  const expected = JSON.parse(
    await readFile(new URL('expected.json', LANGUAGE_FIXTURES), 'utf8')
  );
  const names = (await readdir(LANGUAGE_FIXTURES))
    .filter((name) => name.endsWith('.yaml'))
    .sort();
  assert.deepEqual(names, Object.keys(expected).sort());

  for (const name of names) {
    const content = await readFile(new URL(name, LANGUAGE_FIXTURES), 'utf8');
    assert.deepEqual(readLanguageSetting(content), expected[name], name);
  }
});

test('explicit malformed language settings are detected rather than ignored', () => {
  assert.deepEqual(readLanguageSetting('language:\n'), {
    present: true,
    raw: '',
    duplicate: false
  });
  assert.deepEqual(readLanguageSetting('language: en-US#not-a-comment\n'), {
    present: true,
    raw: 'en-US#not-a-comment',
    duplicate: false
  });
  assert.deepEqual(readLanguageSetting('language: "en-US" extra\n'), {
    present: true,
    raw: '"en-US" extra',
    duplicate: false
  });
  assert.deepEqual(
    readLanguageSetting('language: "en-US"\nlanguage: "zh-CN"\n'),
    { present: true, raw: null, duplicate: true }
  );
});

test('readProjectLanguage defaults on a missing config and reports invalid values', async (t) => {
  const target = await createTempDir(t);
  const missing = await readProjectLanguage(target);
  assert.deepEqual(
    { present: missing.present, valid: missing.valid, language: missing.language },
    { present: false, valid: true, language: DEFAULT_LANGUAGE }
  );

  const configFile = join(target, '.cowork-flow', 'config.yaml');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(configFile, 'codex:\n  dispatch_mode: inline\n', 'utf8');
  const missingKey = await readProjectLanguage(target);
  assert.equal(missingKey.present, true);
  assert.equal(missingKey.configured, false);
  assert.equal(missingKey.valid, true);
  assert.equal(missingKey.language, DEFAULT_LANGUAGE);

  await writeFile(configFile, 'language: "fr"\n', 'utf8');
  const invalid = await readProjectLanguage(target);
  assert.equal(invalid.present, true);
  assert.equal(invalid.valid, false);
  assert.equal(invalid.raw, 'fr');
  assert.equal(invalid.language, DEFAULT_LANGUAGE);
});

test('strict language reading rejects empty, glued, trailing, and duplicate values', async (t) => {
  const target = await createTempDir(t);
  const configFile = join(target, '.cowork-flow', 'config.yaml');
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  const cases = [
    'language:\n',
    'language: en-US#not-a-comment\n',
    'language: "en-US" extra\n',
    'language: "en-US"\nlanguage: "zh-CN"\n'
  ];
  for (const content of cases) {
    await writeFile(configFile, content, 'utf8');
    await assert.rejects(
      readProjectLanguageStrict(target),
      /unsupported language|duplicate language keys/
    );
  }
});

test('withLanguage replaces the scalar or appends it when absent', () => {
  assert.equal(
    withLanguage('# config\nlanguage: "zh-CN"\ncodex:\n  dispatch_mode: inline\n', 'en'),
    '# config\nlanguage: "en-US"\ncodex:\n  dispatch_mode: inline\n'
  );
  assert.equal(
    withLanguage('# config\ncodex:\n  dispatch_mode: inline\n', 'en-US'),
    '# config\ncodex:\n  dispatch_mode: inline\n\nlanguage: "en-US"\n'
  );
  assert.throws(() => withLanguage('', 'fr'), /Unsupported language/);
});

test('localizedSource selects only declared assets and rejects missing files', () => {
  assert.equal(
    hostRegistry.localizedSource(PLAN_TEMPLATE, 'en-US'),
    `locales/en-US/${PLAN_TEMPLATE}`
  );
  assert.equal(hostRegistry.localizedSource(PLAN_TEMPLATE, 'zh-CN'), PLAN_TEMPLATE);
  assert.equal(hostRegistry.localizedSource('.cowork-flow/run', 'en-US'), '.cowork-flow/run');
  assert.throws(
    () => hostRegistry.localizedSource(PLAN_TEMPLATE, 'fr'),
    /Unsupported language/
  );
  assert.equal(
    hostRegistry.shouldInclude(`locales/en-US/${PLAN_TEMPLATE}`, ['codex']),
    false
  );

  const manifest = structuredClone(loadHostAssetManifest());
  manifest.localization.assets['en-US'] = ['.cowork-flow/missing-locale.md'];
  const registry = createHostRegistry(manifest);
  assert.throws(
    () => registry.localizedSource('.cowork-flow/missing-locale.md', 'en-US'),
    /Missing localized asset/
  );
});

test('init distributes the locale assets selected by language', async (t) => {
  const englishTarget = join(await createTempDir(t), 'en');
  await initProject(englishTarget, 'en-US');

  for (const relativePath of [PLAN_TEMPLATE, ANCHOR]) {
    assert.equal(
      await readText(join(englishTarget, ...relativePath.split('/'))),
      (await readFile(localizedAsset(relativePath), 'utf8')).replaceAll('\r\n', '\n')
    );
  }
  assert.equal(await exists(join(englishTarget, 'locales')), false);
  assert.match(
    await readText(join(englishTarget, '.cowork-flow', 'config.yaml')),
    /^language: "en-US"$/m
  );

  const chineseTarget = join(await createTempDir(t), 'zh');
  await initProject(chineseTarget, null);

  for (const relativePath of [PLAN_TEMPLATE, ANCHOR]) {
    assert.equal(
      await readText(join(chineseTarget, ...relativePath.split('/'))),
      (await readFile(baseAsset(relativePath), 'utf8')).replaceAll('\r\n', '\n')
    );
  }
});

test('sync switches both localized assets when the config language changes', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await initProject(target, 'en-US');
  const configFile = join(target, '.cowork-flow', 'config.yaml');

  await writeFile(
    configFile,
    (await readFile(configFile, 'utf8')).replace(/^language: .*$/m, 'language: "zh-CN"'),
    'utf8'
  );
  const zhIo = createIo();
  assert.equal(await main(['sync', target], { io: zhIo }), 0, zhIo.stderr);
  for (const relativePath of [PLAN_TEMPLATE, ANCHOR]) {
    assert.equal(
      await readText(join(target, ...relativePath.split('/'))),
      (await readFile(baseAsset(relativePath), 'utf8')).replaceAll('\r\n', '\n')
    );
  }

  await writeFile(
    configFile,
    (await readFile(configFile, 'utf8')).replace(/^language: .*$/m, 'language: "en-US"'),
    'utf8'
  );
  const enIo = createIo();
  assert.equal(await main(['sync', target], { io: enIo }), 0, enIo.stderr);
  for (const relativePath of [PLAN_TEMPLATE, ANCHOR]) {
    assert.equal(
      await readText(join(target, ...relativePath.split('/'))),
      (await readFile(localizedAsset(relativePath), 'utf8')).replaceAll('\r\n', '\n')
    );
  }
});

test('sync fails before planning on an unsupported config language', async (t) => {
  const target = join(await createTempDir(t), 'demo');
  await initProject(target, 'en-US');
  const anchor = join(target, ...ANCHOR.split('/'));
  const before = await readText(anchor);
  await writeFile(
    join(target, '.cowork-flow', 'config.yaml'),
    'language: "fr"\n',
    'utf8'
  );
  const io = createIo();

  const code = await main(['sync', target], { io });

  assert.equal(code, 1);
  assert.match(io.stderr, /unsupported language "fr"/i);
  assert.equal(await readText(anchor), before);
});

test('dev refresh fails before planning on an unsupported config language', async (t) => {
  const target = await createTempDir(t);
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  await writeFile(
    join(target, '.cowork-flow', 'config.yaml'),
    'language: "fr"\n',
    'utf8'
  );
  const io = createIo();

  const code = await main(['dev', 'refresh', target], { io });

  assert.equal(code, 1);
  assert.match(io.stderr, /unsupported language "fr"/i);
});

test('dev refresh uses the configured locale for localized assets', async (t) => {
  const target = await createTempDir(t);
  const anchor = join(target, ...ANCHOR.split('/'));
  await mkdir(join(target, '.cowork-flow', 'spec', 'contracts'), { recursive: true });
  await writeFile(anchor, 'stale anchor\n', 'utf8');
  await writeFile(
    join(target, '.cowork-flow', 'config.yaml'),
    'language: "en-US"\n',
    'utf8'
  );
  const io = createIo();

  const code = await main(['dev', 'refresh', target], { io });

  assert.equal(code, 0, io.stderr);
  assert.equal(
    await readText(anchor),
    (await readFile(localizedAsset(ANCHOR), 'utf8')).replaceAll('\r\n', '\n')
  );
  assert.equal(
    await readText(join(target, ...PLAN_TEMPLATE.split('/'))),
    (await readFile(localizedAsset(PLAN_TEMPLATE), 'utf8')).replaceAll('\r\n', '\n')
  );
});

test('localized contracts and plan templates keep equivalent section structure', async () => {
  const baseAnchor = await readFile(baseAsset(ANCHOR), 'utf8');
  const enAnchor = await readFile(localizedAsset(ANCHOR), 'utf8');
  const basePlan = await readFile(baseAsset(PLAN_TEMPLATE), 'utf8');
  const enPlan = await readFile(localizedAsset(PLAN_TEMPLATE), 'utf8');

  const headings = (text) => [...text.replace(/```[\s\S]*?```/g, '').matchAll(/^## (.+)$/gm)].map((match) => match[1]);
  assert.equal(headings(baseAnchor).length, headings(enAnchor).length);
  assert.equal(headings(basePlan).length, headings(enPlan).length);
  assert.deepEqual(headings(baseAnchor), [
    'Schema',
    'Section requirements',
    'Scenarios',
    'Artifact compression',
    'Lifecycle check coupling',
    'Formal-release behavior'
  ]);
  assert.deepEqual(headings(enAnchor), headings(baseAnchor));
  const planSections = [['目标', 'Goal'], ['验收标准', 'Acceptance Criteria'],
    ['全局约束', 'Global Constraints'], ['文件边界', 'File Boundaries'],
    ['任务', 'Tasks'], ['最终验证', 'Final Verification']];
  assert.deepEqual(headings(basePlan), planSections.map(([zh]) => zh));
  assert.deepEqual(headings(enPlan), planSections.map(([, en]) => en));
});
