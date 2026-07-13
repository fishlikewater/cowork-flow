import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

import { buildInitPlan } from '../src/lib/copy-template.js';


const ROOT = fileURLToPath(new URL('..', import.meta.url));
const MODULE_URL = new URL('../src/lib/skill-registry.js', import.meta.url);
const REGISTRY_PATH = join(
  ROOT,
  'template',
  '.cowork-flow',
  'spec',
  'runtime',
  'skill-registry.json'
);
const SCHEMA_PATH = join(
  ROOT,
  'template',
  '.cowork-flow',
  'spec',
  'schemas',
  'skill-registry.schema.json'
);
const README_PATH = join(ROOT, 'README.md');


async function loadModule() {
  assert.equal(
    existsSync(fileURLToPath(MODULE_URL)),
    true,
    'AC-002 requires the Node Skill Registry loader'
  );
  return import(MODULE_URL.href);
}


function registryFixture() {
  return {
    schemaVersion: 1,
    entries: [
      {
        id: 'workflow-readiness',
        displayName: 'Workflow Readiness',
        aliases: [],
        kind: 'runtime',
        visibility: 'internal',
        status: 'active',
        statuses: [],
        intents: [],
        enforcement: 'runtime',
        runtimeGate: null,
        runtimeCommand: 'task next',
        evidenceArtifact: null,
        source: '.cowork-flow/scripts/common/task/readiness.py',
        managedPaths: []
      },
      {
        id: 'example',
        displayName: 'Example',
        aliases: [],
        kind: 'phase',
        visibility: 'public',
        status: 'active',
        statuses: ['planning'],
        intents: ['example_intent'],
        enforcement: 'advisory',
        runtimeGate: null,
        runtimeCommand: null,
        evidenceArtifact: null,
        source: 'skills/brainstorming/SKILL.md',
        managedPaths: [
          '.agents/skills/example/',
          '.claude/skills/example/'
        ]
      }
    ]
  };
}


test('canonical skill registry and schema load', async () => {
  assert.equal(existsSync(REGISTRY_PATH), true, 'AC-002 requires Registry JSON');
  assert.equal(existsSync(SCHEMA_PATH), true, 'AC-002 requires Registry schema');
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8'));
  assert.equal(schema.$schema, 'https://json-schema.org/draft/2020-12/schema');
  assert.equal(schema.additionalProperties, false);

  const { loadSkillRegistry } = await loadModule();
  const registry = loadSkillRegistry();

  assert.equal(registry.schemaVersion, 1);
  assert.deepEqual(
    registry.publicSkillIds,
    [...registry.publicSkillIds].sort()
  );
  assert.equal(registry.publicSkillIds.includes('batch-mode'), true);
  assert.equal(registry.publicSkillIds.includes('doubt-review'), true);
  assert.equal(registry.publicSkillIds.includes('game-design'), true);
  for (const removedSkillId of [
    'before-dev',
    'start',
    'continue',
    'finish-work',
    'using-cowork-flow'
  ]) {
    assert.equal(registry.entry(removedSkillId), null, removedSkillId);
  }
});

test('README public Skill list matches the canonical Registry', async () => {
  const { loadSkillRegistry } = await loadModule();
  const registry = loadSkillRegistry();
  const readme = readFileSync(README_PATH, 'utf8');
  const match = readme.match(/^分发动作：(.+)$/m);

  assert.notEqual(match, null);
  const documented = match[1]
    .split('、')
    .map((item) => item.trim().replaceAll('`', ''))
    .sort();
  assert.deepEqual(documented, registry.publicSkillIds);
});


test('semantic validation rejects duplicate ids and aliases', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries.push({
    ...structuredClone(raw.entries[1]),
    id: 'other',
    aliases: ['example'],
    intents: ['other_intent'],
    managedPaths: [
      '.agents/skills/other/',
      '.claude/skills/other/'
    ]
  });

  assert.throws(
    () => createSkillRegistry(raw),
    /duplicate skill id or alias: example/
  );
});


test('schema validation rejects invalid enums', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries[1].kind = 'unknown';

  assert.throws(
    () => createSkillRegistry(raw),
    /invalid kind for example: unknown/
  );
});


test('formal registry rejects removed lifecycle fields', async () => {
  const { createSkillRegistry } = await loadModule();
  const deprecated = registryFixture();
  deprecated.entries[1].status = 'deprecated';

  assert.throws(
    () => createSkillRegistry(deprecated),
    /invalid status for example: deprecated/
  );

  const replacement = registryFixture();
  replacement.entries[1].replacement = 'workflow-readiness';
  assert.throws(
    () => createSkillRegistry(replacement),
    /unexpected field for example: replacement/
  );
});


test('mandatory entries require a runtime gate', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries[1].enforcement = 'mandatory';

  assert.throws(
    () => createSkillRegistry(raw),
    /mandatory entry example requires runtimeGate/
  );
});


test('runtime gates must reference runtime entries', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries[1].enforcement = 'mandatory';
  raw.entries[1].runtimeGate = 'example';

  assert.throws(
    () => createSkillRegistry(raw),
    /runtimeGate example must reference a runtime entry/
  );
});


test('semantic validation rejects missing sources', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries[1].source = 'skills/missing/SKILL.md';

  assert.throws(
    () => createSkillRegistry(raw),
    /source does not exist for example: skills\/missing\/SKILL.md/
  );
});


test('semantic validation rejects overlapping managed paths', async () => {
  const { createSkillRegistry } = await loadModule();
  const raw = registryFixture();
  raw.entries.push({
    ...structuredClone(raw.entries[1]),
    id: 'nested',
    intents: ['nested_intent'],
    managedPaths: ['.agents/skills/example/nested/']
  });

  assert.throws(
    () => createSkillRegistry(raw),
    /managed path overlap/
  );
});


test('init plan distributes only active public registry skills', async () => {
  const { loadSkillRegistry } = await loadModule();
  const registry = loadSkillRegistry();
  const targetDir = await mkdtemp(join(tmpdir(), 'cowork-skill-registry-'));
  try {
    const plan = await buildInitPlan(targetDir, {
      platforms: ['codex'],
      version: 'test'
    });
    const skillIds = plan.actions
      .map((action) => action.relativePath.replaceAll('\\', '/'))
      .filter((path) => (
        path.startsWith('.agents/skills/')
        && path.endsWith('/SKILL.md')
      ))
      .map((path) => path.split('/')[2])
      .sort();

    assert.deepEqual(skillIds, registry.publicSkillIds);
  } finally {
    await rm(targetDir, { recursive: true, force: true });
  }
});
