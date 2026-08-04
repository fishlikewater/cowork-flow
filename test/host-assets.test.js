import assert from 'node:assert/strict';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  createHostRegistry,
  loadHostAssetManifest
} from '../src/lib/host-assets.js';


const TEMPLATE_SKILLS_DIR = new URL('../template/skills/', import.meta.url);


function templateSkillIds() {
  return readdirSync(TEMPLATE_SKILLS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => existsSync(join(TEMPLATE_SKILLS_DIR.pathname, name, 'SKILL.md')))
    .sort();
}


test('default host registry exposes manifest platform behavior', () => {
  const manifest = loadHostAssetManifest();
  const registry = createHostRegistry(manifest);

  assert.deepEqual(registry.platformIds, ['codex', 'opencode', 'claude-code']);
  assert.deepEqual(
    registry.parsePlatformSelection(['claude']),
    ['claude-code']
  );
  assert.equal(registry.platformLabel('opencode'), 'OpenCode');
  assert.equal(registry.skillDestination('claude-code'), '.claude/skills');
  assert.equal(
    registry.shouldInclude('.codex/hooks.json', ['codex']),
    true
  );
  assert.equal(
    registry.shouldInclude('.codex/hooks.json', ['opencode']),
    false
  );
  assert.equal(registry.shouldInclude('skills/start/SKILL.md', ['codex']), false);
  assert.deepEqual(registry.assetOwners('.codex/hooks.json'), ['codex']);
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/adapters/claude-code/adapter.yaml'),
    ['claude-code']
  );
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/config.yaml'), true);
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/run'), false);
  assert.equal(registry.isSafeSyncFile('.codex/hooks.json'), true);
  assert.equal(registry.isManagedBlockFile('AGENTS.md'), true);
  assert.equal(
    registry.obsoleteSyncFiles().includes('.cowork-flow/workflow.md'),
    true
  );
});


test('a simulated platform is added by manifest data only', () => {
  const manifest = loadHostAssetManifest();
  manifest.platforms.push({
    id: 'demo-host',
    displayName: 'Demo Host',
    aliases: ['demo', 'demo-host'],
    detectAny: ['.demo-host'],
    assetPrefixes: ['.demo-host/'],
    assetFiles: [],
    skillTarget: '.demo-host/skills',
    adapterPath: '.cowork-flow/adapters/demo-host/adapter.yaml',
    capabilities: {
      dispatchSubagent: 'external'
    },
    commandTargets: []
  });
  const registry = createHostRegistry(manifest);

  assert.deepEqual(registry.parsePlatformSelection(['demo']), ['demo-host']);
  assert.equal(registry.platformLabel('demo-host'), 'Demo Host');
  assert.equal(
    registry.shouldInclude('.demo-host/config.json', ['demo-host']),
    true
  );
  assert.equal(
    registry.shouldInclude('.demo-host/config.json', ['codex']),
    false
  );
  assert.equal(
    registry.skillDestination('demo-host'),
    '.demo-host/skills'
  );
});


test('active public skills are not obsolete sync targets', () => {
  const manifest = loadHostAssetManifest();
  const registry = createHostRegistry(manifest);
  const obsoleteFiles = new Set(registry.syncPolicy.obsoleteFiles);

  for (const skillId of templateSkillIds()) {
    for (const target of registry.skillTargets) {
      assert.equal(
        obsoleteFiles.has(`${target}/${skillId}`),
        false,
        skillId
      );
      assert.equal(
        obsoleteFiles.has(`${target}/${skillId}/SKILL.md`),
        false,
        skillId
      );
    }
  }
});
