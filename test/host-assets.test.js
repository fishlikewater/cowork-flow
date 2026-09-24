import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  createHostRegistry,
  loadHostAssetManifest
} from '../src/lib/host-assets.js';
import { packageRoot } from '../src/lib/paths.js';


const TEMPLATE_SKILLS_DIR = new URL('../template/skills/', import.meta.url);

const HOST_MANIFEST_FIXTURES = new URL('../tests/fixtures/host-manifest/', import.meta.url);
const VALID_MANIFEST_FIXTURES = ['valid-minimal.json', 'valid-extra-platform.json'];
const INVALID_MANIFEST_FIXTURES = new Map([
  ['invalid-duplicate-alias.json', /duplicate platform alias/i],
  ['invalid-capability-status.json', /illegal host-neutral capability/i],
  ['invalid-capability-value.json', /capabilityValues/i],
  ['invalid-unsupported-without-fallback.json', /unsupported capability requires fallback/i],
  ['invalid-unknown-field.json', /unknown field/i],
  ['invalid-missing-matrix-host.json', /missing host/i]
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
        skillReadRoot: platform.skillReadRoot,
        skillDiscovery: platform.skillDiscovery,
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
  assert.equal(extra.assets['demo-host'].skillReadRoot, '.demo-host/skills');
  assert.deepEqual(extra.assets['demo-host'].skillDiscovery, [
    { scope: 'project', path: '.demo-host/skills', evidence: 'test fixture' }
  ]);
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

  assert.deepEqual(
    registry.platformIds,
    ['codex', 'opencode', 'claude-code', 'dsh', 'zcode', 'kimi-code', 'qoder']
  );
  assert.deepEqual(
    registry.parsePlatformSelection(['claude']),
    ['claude-code']
  );
  assert.deepEqual(registry.parsePlatformSelection(['zcode']), ['zcode']);
  assert.deepEqual(registry.parsePlatformSelection(['kimi']), ['kimi-code']);
  assert.equal(registry.platformLabel('opencode'), 'OpenCode');
  assert.equal(registry.platformLabel('zcode'), 'ZCode');
  assert.equal(registry.platformLabel('kimi-code'), 'Kimi Code');
  assert.equal(registry.skillDestination('claude-code'), '.claude/skills');
  assert.equal(registry.skillDestination('dsh'), '.agents/skills');
  assert.equal(registry.skillDestination('zcode'), '.agents/skills');
  assert.equal(registry.skillDestination('kimi-code'), '.agents/skills');
  // ZCode enumerates `.agents/skills` too (host bundle-verified), so it shares
  // the project copy like the other agents-directory hosts; the private
  // `.cowork-flow/skills` replica is now owned by nobody.
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/skills/cowork-flow/SKILL.md'),
    []
  );
  assert.deepEqual(registry.assetOwners('.dsh/README.md'), ['dsh']);
  assert.equal(registry.shouldInclude('.dsh/README.md', ['codex']), false);
  assert.deepEqual(registry.parsePlatformSelection(['dsh']), ['dsh']);
  // Kimi Code hooks live in the user-level $KIMI_CODE_HOME/config.toml, so the
  // platform must declare no project-level command target at all.
  assert.deepEqual(registry.platform('kimi-code').commandTargets, []);
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
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/adapters/kimi-code/adapter.yaml'),
    ['kimi-code']
  );
  assert.deepEqual(
    registry.assetOwners('.kimi-code/agents/cowork-implement.md'),
    ['kimi-code']
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
    registry.shouldInclude('.cowork-flow/adapters/kimi-code/adapter.yaml', ['kimi-code']),
    true
  );
  assert.equal(
    registry.shouldInclude('.kimi-code/agents/cowork-implement.md', ['kimi-code']),
    true
  );
  assert.equal(
    registry.shouldInclude('.kimi-code/agents/cowork-implement.md', ['codex']),
    false
  );
  assert.equal(
    registry.shouldInclude('.zcode/hooks/inject-context.js', ['zcode']),
    false
  );
  assert.deepEqual(registry.parsePlatformSelection(['qoder-cli']), ['qoder']);
  assert.equal(registry.platformLabel('qoder'), 'Qoder');
  assert.equal(registry.skillDestination('qoder'), '.agents/skills');
  assert.deepEqual(registry.platform('qoder').skillDiscovery, [
    {
      scope: 'project',
      path: '.agents/skills',
      gates: ['trusted-folder', 'restart'],
      evidence: registry.platform('qoder').skillDiscovery[0].evidence
    }
  ]);
  assert.match(registry.platform('qoder').skillDiscovery[0].evidence, /^verified:/);
  assert.deepEqual(registry.platform('qoder').commandTargets, []);
  // Qoder ships hooks/agents/commands inside a machine-level plugin, so nothing
  // under `.qoder/` may reach a project even when qoder is the selected platform.
  assert.equal(registry.shouldInclude('.qoder/settings.json', ['qoder']), false);
  assert.equal(
    registry.shouldInclude('.qoder/agents/cowork-implement.md', ['qoder']),
    false
  );
  assert.equal(registry.isSafeSyncFile('.qoder/settings.json'), false);
  assert.deepEqual(
    registry.assetOwners('.cowork-flow/adapters/qoder/adapter.yaml'),
    ['qoder']
  );
  assert.equal(
    registry.shouldInclude('.cowork-flow/adapters/qoder/adapter.yaml', ['qoder']),
    true
  );
  assert.equal(
    registry.shouldInclude('.cowork-flow/adapters/qoder/adapter.yaml', ['codex']),
    false
  );
  // The private replica is nobody's asset now: ZCode reads the shared
  // `.agents/skills` like the other agents-directory hosts.
  assert.equal(
    registry.shouldInclude('.agents/skills/agent-dispatch/SKILL.md', ['zcode']),
    true
  );
  const detected = await registry.detectInstalledPlatforms(
    '/tmp/fake-target',
    // path.join is platform-specific; compare with separators normalized so
    // the mock exists-check matches on win32 as well as POSIX.
    (candidate) => candidate.replaceAll('\\', '/') === '/tmp/fake-target/.zcode'
  );
  assert.deepEqual(detected, ['zcode']);
  assert.deepEqual(
    await registry.detectInstalledPlatforms(
      '/tmp/fake-target',
      (candidate) => candidate.replaceAll('\\', '/') === '/tmp/fake-target/.kimi-code'
    ),
    ['kimi-code']
  );
  // Qoder is detected through its adapter declaration, never through a
  // project-level `.qoder/` directory the user may own for unrelated reasons.
  assert.deepEqual(
    await registry.detectInstalledPlatforms(
      '/tmp/fake-target',
      (candidate) =>
        candidate.replaceAll('\\', '/') ===
        '/tmp/fake-target/.cowork-flow/adapters/qoder'
    ),
    ['qoder']
  );
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/config.yaml'), true);
  assert.equal(registry.isProtectedSyncFile('.cowork-flow/run'), false);
  assert.equal(registry.isSafeSyncFile('.codex/hooks.json'), true);
  assert.equal(registry.isSafeSyncFile('.kimi-code/agents/cowork-check.md'), true);
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
  assert.deepEqual(
    registry.hostCapability('kimi-code', 'party_board_action'),
    {
      status: 'unsupported',
      fallback: 'inline_or_manual'
    }
  );
  for (const action of registry.capabilityMatrix.required) {
    assert.equal(
      registry.hostCapability('qoder', action).status,
      'native',
      `qoder must declare ${action} natively`
    );
  }
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
    skillReadRoot: '.demo-host/skills',
    skillDiscovery: [
      { scope: 'project', path: '.demo-host/skills', evidence: 'simulated platform' }
    ],
    adapterPath: '.cowork-flow/adapters/demo-host/adapter.yaml',
    capabilities: {
      dispatchSubagent: 'external'
    },
    commandTargets: [],
    payload: { source: 'presets/demo-host', manifest: '.demo-host-plugin/plugin.json' }
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
  assert.deepEqual(
    registry.platformPayload('demo-host'),
    {
      sourceDir: join(packageRoot, 'presets', 'demo-host'),
      manifest: '.demo-host-plugin/plugin.json'
    }
  );
});


test('declared payloads resolve to directories the package really ships', () => {
  const manifest = loadHostAssetManifest();
  const registry = createHostRegistry(manifest);
  const declared = manifest.platforms.filter((platform) => platform.payload);

  // Every other host installs a preset or a hook, not a plugin payload; a new
  // entry here without a matching presets/ directory must fail below.
  assert.deepEqual(
    declared.map((platform) => platform.id),
    ['codex', 'opencode', 'claude-code', 'zcode', 'kimi-code', 'qoder']
  );
  for (const platform of declared) {
    const payload = registry.platformPayload(platform.id);
    assert.equal(payload.sourceDir, join(packageRoot, 'presets', platform.id));
    if (!payload.manifest) {
      // opencode's plugin format has no manifest, so there is nothing inside the
      // payload to point at. Every other payload must name one.
      assert.equal(platform.id, 'opencode');
      assert.ok(existsSync(join(payload.sourceDir, 'plugins', 'cowork-flow.js')));
      continue;
    }
    assert.ok(
      existsSync(join(payload.sourceDir, ...payload.manifest.split('/'))),
      `${platform.id} declares ${payload.manifest}, which must exist inside ${platform.payload.source}`
    );
  }
  assert.equal(registry.platformPayload('dsh'), null);
});


test('plugin installers locate their payload through the declaration', () => {
  const manifest = loadHostAssetManifest();
  for (const host of ['opencode', 'codex', 'claude-code', 'zcode', 'kimi-code', 'qoder']) {
    const installer = readFileSync(
      join(packageRoot, 'src', 'commands', `install-${host}-plugin.js`),
      'utf8'
    );
    // Comments may name the shipped directory; the code must not, in any
    // quoting style (a template literal would slip past a quoted-literal match).
    assert.doesNotMatch(
      installer.replace(/^\s*\/\/.*$/gm, ''),
      /presets/,
      `install-${host}-plugin.js must resolve its payload directory from the declaration`
    );
    assert.match(installer, /(?:pluginPayload|payloadSourceDir)\(/);
    const declared = manifest.platforms.find((platform) => platform.id === host).payload;
    if (!declared.manifest) {
      // A manifestless payload has nothing to stamp, and the installer must not
      // pretend otherwise: it resolves only the directory.
      assert.doesNotMatch(
        installer,
        /stampPayloadManifest\(/,
        `${host} has no payload manifest, so it must not stamp one`
      );
      continue;
    }
    assert.match(
      installer,
      /stampPayloadManifest\(/,
      `install-${host}-plugin.js must stamp the manifest it declares`
    );
  }
});


test('host registry rejects malformed payload declarations', () => {
  const manifest = loadHostAssetManifest();
  const withCodexPayload = (payload) => {
    const broken = structuredClone(manifest);
    const codex = broken.platforms.find((platform) => platform.id === 'codex');
    if (payload === undefined) {
      delete codex.payload;
    } else {
      codex.payload = payload;
    }
    return broken;
  };

  assert.throws(
    () => createHostRegistry(withCodexPayload('presets/codex')),
    /platform codex payload must be null or an object/
  );
  assert.throws(
    () => createHostRegistry(withCodexPayload(undefined)),
    /platform codex payload must be null or an object/
  );
  assert.throws(
    () => createHostRegistry(withCodexPayload({ manifest: '.codex-plugin/plugin.json' })),
    /platform codex payload\.source must be a non-empty string/
  );
  assert.throws(
    () => createHostRegistry(withCodexPayload({ source: 'presets/codex', skills: 'skills' })),
    /platform codex payload unknown field: skills/
  );
  // An explicit null manifest is a bad value, not "no manifest": only the
  // missing key means the payload carries none.
  assert.throws(
    () => createHostRegistry(withCodexPayload({ source: 'presets/codex', manifest: null })),
    /platform codex payload\.manifest must be a non-empty string/
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
    for (const target of registry.skillReadRoots) {
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

test('host registry rejects malformed skill declarations', () => {
  const platformById = (manifest, id) =>
    manifest.platforms.find((platform) => platform.id === id);
  const cases = [
    [
      'empty evidence',
      (manifest) => {
        platformById(manifest, 'qoder').skillDiscovery[0].evidence = '';
      },
      /skillDiscovery evidence/i
    ],
    [
      'unknown scope',
      (manifest) => {
        platformById(manifest, 'qoder').skillDiscovery[0].scope = 'global';
      },
      /skillDiscovery scope/i
    ],
    [
      'project path differs from readRoot',
      (manifest) => {
        platformById(manifest, 'qoder').skillDiscovery[0].path = '.qoder/skills';
      },
      /must equal skillReadRoot/i
    ],
    [
      'machine scope is no longer a declared discovery channel',
      (manifest) => {
        platformById(manifest, 'zcode').skillDiscovery.push({
          scope: 'machine',
          evidence: 'verified: synthetic machine channel for this test'
        });
      },
      /skillDiscovery scope/i
    ],
    [
      'channel is no longer a discovery field',
      (manifest) => {
        platformById(manifest, 'qoder').skillDiscovery[0].channel = 'plugin:skills';
      },
      /skillDiscovery unknown field/i
    ],
    [
      'empty discovery array',
      (manifest) => {
        platformById(manifest, 'qoder').skillDiscovery = [];
      },
      /skillDiscovery must be a non-empty array/i
    ],
    [
      'missing readRoot',
      (manifest) => {
        delete platformById(manifest, 'qoder').skillReadRoot;
      },
      /skillReadRoot/i
    ]
  ];

  for (const [label, mutate, expected] of cases) {
    const manifest = loadHostAssetManifest();
    mutate(manifest);
    assert.throws(() => createHostRegistry(manifest), expected, label);
  }
});
