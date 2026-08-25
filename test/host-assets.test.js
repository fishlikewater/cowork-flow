import assert from 'node:assert/strict';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  createHostRegistry,
  loadHostAssetManifest
} from '../src/lib/host-assets.js';


const TEMPLATE_SKILLS_DIR = new URL('../template/skills/', import.meta.url);

const HOST_MANIFEST_FIXTURES = new URL('../tests/fixtures/host-manifest/', import.meta.url);
const VALID_MANIFEST_FIXTURES = ['valid-minimal.json', 'valid-extra-platform.json'];
const INVALID_MANIFEST_FIXTURES = new Map([
  ['invalid-duplicate-alias.json', /duplicate platform alias/i],
  ['invalid-capability-status.json', /illegal host-neutral capability/i],
  ['invalid-capability-value.json', /capabilityValues/i],
  ['invalid-unsupported-without-fallback.json', /unsupported capability requires fallback/i],
  ['invalid-unknown-field.json', /unknown field/i]
]);
const ALL_MANIFEST_FIXTURES = [
  ...VALID_MANIFEST_FIXTURES,
  ...INVALID_MANIFEST_FIXTURES.keys()
].sort();
const REQUIRED_HOST_NEUTRAL_CAPABILITIES = [
  'task_action',
  'subagent_dispatch',
  'file_write',
  'party_board_action'
];

function fixtureUrl(name) {
  return new URL(name, HOST_MANIFEST_FIXTURES);
}

function loadFixtureRegistry(name) {
  return createHostRegistry(loadHostAssetManifest(fixtureUrl(name)));
}

function registryContractSummary(registry) {
  return {
    schemaVersion: registry.manifest.schemaVersion,
    platformIds: registry.platformIds,
    aliasOwners: Object.fromEntries(
      registry.platforms.flatMap(
        (platform) => platform.aliases.map((alias) => [alias, platform.id])
      ).sort(([left], [right]) => left.localeCompare(right))
    ),
    assets: Object.fromEntries(registry.platforms.map((platform) => [
      platform.id,
      {
        assetPrefixes: platform.assetPrefixes,
        assetFiles: platform.assetFiles,
        skillTarget: platform.skillTarget,
        commandTargets: platform.commandTargets
      }
    ])),
    syncPolicy: registry.syncPolicy,
    capabilitySummary: Object.fromEntries(
      Object.entries(registry.capabilityMatrix.hosts)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([hostId, capabilities]) => [
          hostId,
          Object.fromEntries(REQUIRED_HOST_NEUTRAL_CAPABILITIES.map((capability) => [
            capability,
            capabilities[capability]
          ]))
        ])
    )
  };
}



function templateSkillIds() {
  return readdirSync(TEMPLATE_SKILLS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => existsSync(join(TEMPLATE_SKILLS_DIR.pathname, name, 'SKILL.md')))
    .sort();
}



test('host manifest fixtures are shared and classified by category', () => {
  assert.deepEqual(
    readdirSync(HOST_MANIFEST_FIXTURES).filter((name) => name.endsWith('.json')).sort(),
    ALL_MANIFEST_FIXTURES
  );
  for (const fixtureName of VALID_MANIFEST_FIXTURES) {
    assert.doesNotThrow(() => loadFixtureRegistry(fixtureName), fixtureName);
  }
  for (const [fixtureName, category] of INVALID_MANIFEST_FIXTURES) {
    assert.throws(
      () => loadFixtureRegistry(fixtureName),
      (error) => {
        assert.match(error.message, category, fixtureName);
        return true;
      }
    );
  }
});


test('valid host manifest fixtures expose normalized registry summaries', () => {
  const minimal = registryContractSummary(loadFixtureRegistry('valid-minimal.json'));
  assert.deepEqual(minimal.platformIds, ['codex']);
  assert.deepEqual(minimal.aliasOwners, { codex: 'codex' });
  assert.deepEqual(minimal.assets.codex.assetPrefixes, ['.codex/']);
  assert.deepEqual(minimal.assets.codex.commandTargets[0], {
    config: '.codex/config.toml',
    format: 'toml',
    target: '.codex/agents/cowork-implement.toml'
  });
  assert.deepEqual(minimal.syncPolicy.managedBlockFiles, ['AGENTS.md']);
  assert.deepEqual(
    minimal.capabilitySummary.zcode.file_write,
    { status: 'unsupported', fallback: 'project_root_init_or_sync' }
  );

  const extra = registryContractSummary(loadFixtureRegistry('valid-extra-platform.json'));
  assert.deepEqual(extra.platformIds, ['codex', 'demo-host']);
  assert.equal(extra.aliasOwners.demo, 'demo-host');
  assert.deepEqual(extra.assets['demo-host'].assetFiles, ['AGENTS.md']);
  assert.equal(extra.assets['demo-host'].skillTarget, '.demo-host/skills');
  assert.deepEqual(extra.assets['demo-host'].commandTargets[0], {
    config: '.demo-host/config.json',
    format: 'json',
    target: '.demo-host/agents/cowork-implement.md'
  });
  assert.deepEqual(
    extra.capabilitySummary['demo-host'].subagent_dispatch,
    { status: 'unsupported', fallback: 'inline_or_manual' }
  );
});

test('default host registry exposes manifest platform behavior', async () => {
  const manifest = loadHostAssetManifest();
  const registry = createHostRegistry(manifest);

  assert.deepEqual(registry.platformIds, ['codex', 'opencode', 'claude-code', 'dsh', 'zcode']);
  assert.deepEqual(
    registry.parsePlatformSelection(['claude']),
    ['claude-code']
  );
  assert.deepEqual(registry.parsePlatformSelection(['zcode']), ['zcode']);
  assert.equal(registry.platformLabel('opencode'), 'OpenCode');
  assert.equal(registry.platformLabel('zcode'), 'ZCode');
  assert.equal(registry.skillDestination('claude-code'), '.claude/skills');
  assert.equal(registry.skillDestination('dsh'), '.agents/skills');
  assert.equal(registry.skillDestination('zcode'), '.cowork-flow/skills');
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/skills/cowork-flow/SKILL.md'),
    ['zcode']
  );
  assert.deepEqual(registry.assetOwners('.dsh/README.md'), ['dsh']);
  assert.equal(registry.shouldInclude('.dsh/README.md', ['codex']), false);
  assert.deepEqual(registry.parsePlatformSelection(['dsh']), ['dsh']);
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
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/adapters/zcode/adapter.yaml'),
    ['zcode']
  );
  assert.equal(
    registry.shouldInclude('.cowork-flow/adapters/zcode/adapter.yaml', ['zcode']),
    true
  );
  assert.equal(
    registry.shouldInclude('.cowork-flow/adapters/zcode/adapter.yaml', ['codex']),
    false
  );
  assert.equal(
    registry.shouldInclude('.zcode/hooks/inject-context.js', ['zcode']),
    false
  );
  const detected = await registry.detectInstalledPlatforms(
    '/tmp/fake-target',
    (candidate) => candidate === '/tmp/fake-target/.zcode'
  );
  assert.deepEqual(detected, ['zcode']);
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/config.yaml'), true);
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/run'), false);
  assert.equal(registry.isSafeSyncFile('.codex/hooks.json'), true);
  assert.equal(registry.isManagedBlockFile('AGENTS.md'), true);
  assert.equal(
    registry.obsoleteSyncFiles().includes('.cowork-flow/workflow.md'),
    true
  );
  assert.deepEqual(
    registry.capabilityMatrix.required,
    ['task_action', 'subagent_dispatch', 'file_write', 'party_board_action']
  );
  assert.deepEqual(
    registry.hostCapability('zcode', 'file_write'),
    {
      status: 'unsupported',
      fallback: 'project_root_init_or_sync'
    }
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
  manifest.capabilityMatrix.hosts['demo-host'] = {
    task_action: {
      status: 'external'
    },
    subagent_dispatch: {
      status: 'unsupported',
      fallback: 'inline_or_manual'
    },
    file_write: {
      status: 'native'
    },
    party_board_action: {
      status: 'unsupported',
      fallback: 'inline_or_manual'
    }
  };
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
  assert.deepEqual(
    registry.hostCapability('demo-host', 'subagent_dispatch'),
    {
      status: 'unsupported',
      fallback: 'inline_or_manual'
    }
  );
});


test('host registry rejects unsupported host-neutral capability without fallback', () => {
  const manifest = loadHostAssetManifest();
  const broken = structuredClone(manifest);
  delete broken.capabilityMatrix.hosts.zcode.file_write.fallback;

  assert.throws(
    () => createHostRegistry(broken),
    /unsupported capability requires fallback: zcode:file_write/
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
