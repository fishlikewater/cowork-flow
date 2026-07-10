import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  createHostRegistry,
  loadHostAssetManifest
} from '../src/lib/host-assets.js';


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
