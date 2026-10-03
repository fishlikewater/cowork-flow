import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { npmCommandOptions } from '../src/lib/package-info.js';
import { loadHostAssetManifest } from '../src/lib/host-assets.js';
import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

test('npm package includes cli source and template assets', async (t) => {
  const npmCache = await mkdtemp(join(tmpdir(), 'cowork-flow-npm-cache-'));
  t.after(async () => {
    await rm(npmCache, { recursive: true, force: true });
  });

  const result = await execFileAsync('npm', ['pack', '--dry-run', '--json'], {
    cwd: packageRoot,
    encoding: 'utf8',
    ...npmCommandOptions(),
    env: {
      ...process.env,
      npm_config_cache: npmCache
    }
  });
  const [pack] = JSON.parse(result.stdout);
  const files = new Set(pack.files.map((file) => file.path));

  assert.equal(files.has('bin/cowork-flow.js'), true);
  assert.equal(files.has('src/cli.js'), true);
  assert.equal(files.has('CHANGELOG.md'), true);
  assert.equal(files.has('template/AGENTS.md'), true);
  assert.equal(files.has('template/CLAUDE.md'), true);
  assert.equal(files.has('template/.cowork-flow/run'), true);
  assert.equal(files.has('template/.cowork-flow/run.cmd'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/run.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/adapters/cli/change.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/entry_classifier.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/infra/git_snapshot.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/services/lifecycle_checks.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/kernel/task_state.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/adapters/review/test_intent.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/coding_standards.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/gates.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/tdd_evidence.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/test_intent.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/spec_validator.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/validate_jsonl.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/common/gates/validate_coding_standards.py'), false);
  assert.equal(files.has('template/.cowork-flow/spec/runtime/rules.json'), false);
  assert.equal(files.has('template/.cowork-flow/spec/schemas/rules.schema.json'), false);
  assert.equal(files.has('template/.cowork-flow/spec/contracts/workflow-state-templates.md'), true);
  assert.equal(files.has('template/.cowork-flow/adapters/claude-code/adapter.yaml'), true);
  assert.equal(files.has('template/.cowork-flow/adapters/dsh/adapter.yaml'), true);
  assert.equal(files.has('template/.cowork-flow/adapters/zcode/adapter.yaml'), true);
  assert.equal(files.has('template/.dsh/README.md'), true);
  assert.equal(files.has('presets/dsh/agent.cordis.yml'), true);
  assert.equal(files.has('presets/dsh/preset.yml'), true);
  assert.equal(files.has('presets/dsh/plugins/workflow-state.js'), true);
  assert.equal(files.has('presets/kimi-code/hooks/cowork-flow-inject.mjs'), true);
  assert.equal(files.has('template/.codex/config.toml'), true);
  assert.equal(files.has('template/.codex/hooks.json'), true);
  assert.equal(files.has('template/.codex/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.claude/agents/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/commands/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/settings.json'), true);
  assert.equal(files.has('template/.claude/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.cowork-flow/adapters/qoder/adapter.yaml'), true);
  assert.equal(files.has('presets/qoder/.qoder-plugin/plugin.json'), true);
  assert.equal(files.has('presets/qoder/hooks/hooks.json'), true);
  assert.equal(files.has('presets/qoder/hooks/inject-context.mjs'), true);
  assert.equal(files.has('presets/qoder/agents/cowork-implement.md'), true);
  assert.equal(files.has('presets/plugin-meta.json'), true);
  assert.equal(files.has('presets/codex/.codex-plugin/plugin.json'), true);
  assert.equal(files.has('presets/codex/skills/cowork-flow-bootstrap/SKILL.md'), true);
  assert.equal(files.has('presets/kimi-code/.kimi-plugin/plugin.json'), true);
  assert.equal(files.has('presets/kimi-code/skills/cowork-flow-bootstrap/SKILL.md'), true);
  assert.equal(files.has('presets/opencode/plugins/cowork-flow.js'), true);
  assert.equal(files.has('presets/opencode/cowork-flow/plugin-core.js'), true);
  assert.equal(files.has('presets/opencode/cowork-flow/skills/cowork-flow-bootstrap/SKILL.md'), true);
  assert.equal(files.has('presets/claude-code/.claude-plugin/plugin.json'), true);
  assert.equal(files.has('presets/claude-code/skills/cowork-flow-bootstrap/SKILL.md'), true);
  // codex resolves interface.logo relative to the plugin root, so the mark has
  // to be inside the payload the host copies — not merely somewhere in the repo.
  assert.equal(files.has('presets/codex/assets/logo.svg'), true);
  assert.equal(files.has('template/.claude/skills/start/SKILL.md'), false);
  assert.equal(files.has('template/.claude/skills/' + 'entry' + '-boundary/SKILL.md'), false);
  assert.equal(files.has('template/.opencode/agents/cowork-implement.md'), true);
  assert.equal(files.has('template/.opencode/commands/cowork-implement.md'), true);
  assert.equal(files.has('template/.opencode/plugins/cowork-flow.js'), true);
  assert.equal(files.has('template/skills/start/SKILL.md'), false);
  assert.equal(files.has('template/skills/before-dev/SKILL.md'), false);
  assert.equal(files.has('template/skills/continue/SKILL.md'), false);
  assert.equal(files.has('template/skills/finish-work/SKILL.md'), false);
  assert.equal(files.has('template/skills/using-cowork-flow/SKILL.md'), false);
  assert.equal(files.has('template/skills/check/SKILL.md'), false);
  assert.equal(files.has('template/skills/test-first/SKILL.md'), true);
  assert.equal(files.has('template/skills/update-spec/SKILL.md'), false);
  assert.equal(files.has('template/skills/adversarial-review/SKILL.md'), true);
  assert.equal(files.has('template/skills/batch-execution/manifest.json'), true);
  assert.equal(files.has('template/skills/brainstorming/manifest.json'), true);
  assert.equal(files.has('template/skills/cowork-flow/manifest.json'), true);
  assert.equal(files.has('template/skills/party-mode/SKILL.md'), true);
  assert.equal(files.has('template/skills/party-mode/manifest.json'), true);
  assert.equal(files.has('template/skills/party-mode/scripts/party_mode_v2.py'), true);
  assert.equal(files.has('template/skills/runtime-health/SKILL.md'), true);
  assert.equal(files.has('template/skills/runtime-health/manifest.json'), true);
  assert.equal(files.has('template/skills/runtime-health/scripts/doctor.py'), true);
  assert.equal(files.has('template/.cowork-flow/scripts/commands/party_mode_v2.py'), false);
  assert.equal(files.has('template/.cowork-flow/scripts/commands/doctor.py'), false);
  assert.equal(files.has('template/skills/party-mode-v2/SKILL.md'), false);
  assert.equal(files.has('template/.cowork-flow/spec/protocols/tdd.md'), false);
  assert.equal(files.has('template/.cowork-flow/spec/protocols/review.md'), false);
  assert.equal(files.has('template/.cowork-flow/spec/protocols/decision-review.md'), false);
  assert.equal(files.has('template/.cowork-flow/spec/protocols/spec-maintenance.md'), false);
  assert.equal(files.has('template/skills/decision-audit/SKILL.md'), true);
  assert.equal(files.has('template/skills/spec-sync/SKILL.md'), true);
  assert.equal(files.has('template/skills/cowork-flow-maintenance/SKILL.md'), true);
  assert.equal(files.has('template/skills/python-runtime-design/SKILL.md'), true);
  assert.equal([...files].some((file) => file.startsWith('template/.superpowers/')), false);
  assert.equal(
    [...files].some((file) => file.includes('__pycache__') || file.endsWith('.pyc')),
    false
  );
});

test('package metadata exposes release script and synchronized lockfile version', async () => {
  const packageInfo = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  const packageLock = JSON.parse(await readFile(join(packageRoot, 'package-lock.json'), 'utf8'));

  assert.equal(packageInfo.scripts.release, 'sh scripts/release.sh');
  assert.equal(packageInfo.scripts['release:check'], 'npm run test:all');
  // The Windows job is the PR buckets plus the suites only test:node:full
  // would otherwise reach; which files those are is asserted by the CI-bucket
  // test below, so this pins the composition and not a copy of the list.
  const windowsCore = packageInfo.scripts['test:windows:core'];
  assert.match(windowsCore, /^npm run test:fast && npm run test:integration && node --test /);
  assert.match(windowsCore, / && npm run pack:check && npm run test:template$/);
  assert.match(packageInfo.scripts['test:all'], /npm run test:node:full/);
  assert.match(packageInfo.scripts['test:all'], /npm run test:template:full/);
  assert.match(packageInfo.scripts['test:all'], /npm run pack:check/);
  // Both names are the same entry point, so whichever one a user types runs
  // the same CLI.
  assert.deepEqual(packageInfo.bin, {
    cwf: './bin/cowork-flow.js',
    'cowork-flow': './bin/cowork-flow.js'
  });
  assert.equal(packageInfo.scripts['source:refresh'], 'node bin/cowork-flow.js dev refresh');
  assert.equal(packageInfo.scripts['source:refresh:dry-run'], 'node bin/cowork-flow.js dev refresh --dry-run');
  assert.equal(packageLock.version, packageInfo.version);
  assert.equal(packageLock.packages[''].version, packageInfo.version);
  // The lockfile records the package identity npm resolves from, and it had
  // drifted: Batch 3 added the `cwf` binary and only package.json learned about
  // it. `npm ci` tolerates the disagreement, so nothing failed and nothing
  // reported it — this assertion is the only thing that keeps the two in step.
  const rootPackage = packageLock.packages[''];
  assert.equal(packageLock.name, packageInfo.name);
  assert.equal(rootPackage.name, packageInfo.name);
  assert.equal(rootPackage.license, packageInfo.license);
  assert.deepEqual(rootPackage.engines, packageInfo.engines);
  assert.deepEqual(
    rootPackage.bin,
    Object.fromEntries(
      Object.entries(packageInfo.bin).map(([name, target]) => [name, target.replace(/^\.\//, '')])
    )
  );
  // Derived from the host asset manifest: the declaration is the single source
  // for which payloads exist and what their manifests are called, so a renamed
  // or added payload cannot leave the release stamping behind.
  const pluginManifests = loadHostAssetManifest()
    .platforms
    .filter((platform) => platform.payload?.manifest)
    .map((platform) => [
      `${platform.payload.source}/${platform.payload.manifest}`,
      platform.id
    ]);
  assert.deepEqual(
    pluginManifests.map(([, host]) => host),
    ['codex', 'claude-code', 'zcode', 'kimi-code', 'qoder']
  );
  const releaseScript = await readFile(join(packageRoot, 'scripts', 'release.sh'), 'utf8');
  for (const [relativePath, host] of pluginManifests) {
    const manifest = JSON.parse(
      await readFile(join(packageRoot, ...relativePath.split('/')), 'utf8')
    );
    assert.equal(
      manifest.version,
      packageInfo.version,
      `${host} plugin version must track the package version`
    );
    assert.ok(
      releaseScript.includes(relativePath),
      `scripts/release.sh must bump the ${host} plugin manifest at ${relativePath}`
    );
  }
  assert.doesNotMatch(
    releaseScript,
    /ZCODE_PLUGIN_JSON=/,
    'bumping must be one rule over every shipped manifest, not one variable per host'
  );
});


test('changelog carries a Keep a Changelog entry for the current package version', async () => {
  const packageInfo = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  const changelog = await readFile(join(packageRoot, 'CHANGELOG.md'), 'utf8');
  const releaseScript = await readFile(join(packageRoot, 'scripts', 'release.sh'), 'utf8');
  // Versions are dotted digits; escape dots for the anchored section header.
  const escaped = packageInfo.version.split('.').join('\.');
  assert.match(
    changelog,
    new RegExp('^## \\[' + escaped + '\\] ', 'm'),
    'CHANGELOG.md must start a bracketed section for the current version (Keep a Changelog)'
  );

  // release.sh greps that same heading before it commits. Bracket one side only
  // and the gate matches nothing while still exiting 0, so take the pattern
  // from the script and run it against the real changelog instead of writing
  // the format out twice.
  const gate = releaseScript.match(/grep -q "([^"]+)" CHANGELOG\.md/);
  assert.ok(gate, 'release.sh must grep CHANGELOG.md for the version heading');
  assert.match(
    changelog,
    new RegExp(gate[1].replace('${PACKAGE_VERSION}', escaped), 'm'),
    `CHANGELOG.md must carry a heading the release gate (${gate[1]}) can find`
  );
});


test('line ending contract keeps javascript sources LF on every checkout', async () => {
  const attributes = await readFile(join(packageRoot, '.gitattributes'), 'utf8');
  // Without this pin a Windows checkout materializes CRLF copies, and the
  // breakage only shows up as a shebang assertion failure on that checkout.
  assert.match(attributes, /^\*\.js text eol=lf$/m);
  assert.match(attributes, /^\*\.mjs text eol=lf$/m);
  // The POSIX runner needs a root-anchored line per copy: a pattern containing
  // "/" is resolved against this file's directory, so `.cowork-flow/run` never
  // matched the template copy that init writes into projects.
  assert.match(attributes, /^\.cowork-flow\/run text eol=lf$/m);
  assert.match(attributes, /^template\/\.cowork-flow\/run text eol=lf$/m);
});


test('CI and publish workflows enforce Windows release confidence gates', async () => {
  const ci = await readFile(join(packageRoot, '.github/workflows/ci.yml'), 'utf8');
  const publish = (await readFile(join(packageRoot, '.github/workflows/publish.yml'), 'utf8'))
    .replaceAll('\r\n', '\n');
  const jobBlock = (jobName) => {
    const marker = `  ${jobName}:\n`;
    const start = publish.indexOf(marker);
    assert.notEqual(start, -1, `missing workflow job: ${jobName}`);
    const bodyStart = start + marker.length;
    const remainder = publish.slice(bodyStart);
    const nextJob = remainder.search(/^  [A-Za-z0-9_-]+:\n/m);
    return nextJob === -1 ? remainder : remainder.slice(0, nextJob);
  };

  assert.match(ci, /windows-core:/);
  assert.match(ci, /runs-on: windows-latest/);
  assert.match(ci, /run: npm run test:windows:core/);
  assert.match(ci, /pip install "pytest>=8"/);
  assert.equal((ci.match(/python -m pytest -q/g) ?? []).length, 2);
  // A pull request must exercise the same gate publish.yml runs before publish.
  assert.match(ci, /run: npm run release:check/);

  const ubuntuVerify = jobBlock('verify-ubuntu');
  const windowsVerify = jobBlock('verify-windows');
  const publishJob = jobBlock('publish');
  assert.match(ubuntuVerify, /run: npm run release:check/);
  assert.match(windowsVerify, /run: npm run release:check/);
  assert.doesNotMatch(ubuntuVerify, /NPM_TOKEN/);
  assert.doesNotMatch(windowsVerify, /NPM_TOKEN/);
  assert.match(publishJob, /needs: \[verify-ubuntu, verify-windows\]/);
  assert.match(publishJob, /NPM_TOKEN/);
  assert.equal((publish.match(/NPM_TOKEN/g) ?? []).length, 1);
});


// `test:node:full` runs everything, so an unlisted file still runs on ubuntu
// through release:check. The Windows PR job is the hole: it runs test:fast +
// test:integration, so a suite nobody names loses Windows coverage until
// publish time. This gate keeps every suite named by some bucket, or exempted
// with a reason.
//
// It does NOT claim per-case Windows coverage. Naming a file is not running all
// of it: test:integration carries --test-name-pattern, so it executes 2 of the
// 43 cases in init.test.js + sync.test.js, and the other 41 only run in the
// ubuntu full pass. The patterned-bucket assertion below keeps that partial
// bucket from spreading.
test('publish workflow binds checkout and package version to an explicit release ref', async () => {
  const publish = (await readFile(join(packageRoot, '.github', 'workflows', 'publish.yml'), 'utf8'))
    .replaceAll('\r\n', '\n');

  assert.match(publish, /workflow_dispatch:\n\s+inputs:/);
  assert.match(publish, /ref:\n\s+description:.*tag/s);
  assert.match(publish, /github\.event\.release\.tag_name/);
  assert.match(publish, /refs\/tags\/v/);
  assert.match(publish, /package\.json/);
  assert.match(publish, /git status --porcelain/);
  assert.match(publish, /npm publish/);
});

test('every node test suite is assigned to a CI bucket', async () => {
  const packageInfo = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));

  // Suites, not every module under test/: helpers/ and fixtures/ are support
  // code that node loads without defining tests. Walked recursively so a nested
  // suite cannot hide, and across the extensions node collects.
  const SUITE = /\.test\.(?:js|mjs|cjs)$/;
  const files = [];
  const walk = async (dir, prefix) => {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (entry.name === 'helpers' || entry.name === 'fixtures') continue;
        await walk(join(dir, entry.name), `${prefix}${entry.name}/`);
      } else if (SUITE.test(entry.name)) {
        files.push(`test/${prefix}${entry.name}`);
      }
    }
  };
  await walk(join(packageRoot, 'test'), '');
  assert.ok(files.length > 0, 'test/ must still hold node suites');

  const scriptFiles = (script) =>
    packageInfo.scripts[script].match(/test\/[\w./-]+\.test\.(?:js|mjs|cjs)/g) ?? [];

  // Exemptions need a reason on the line, so widening this list is a decision
  // rather than a quiet edit. Every entry below skips on Windows by
  // construction; the full run's skip count is what shows that.
  const POSIX_ONLY = new Map([
    ['test/release.test.js', 'drives scripts/release.sh; its cases skip without a POSIX shell runner']
  ]);
  // Windows-sensitive suites: they exercise host installers and spawn-based
  // plumbing, which is where Windows breakage actually shows up.
  const WINDOWS_EXTRAS = [
    'test/dsh-home-patch.test.js',
    'test/dsh-hook.test.js',
    'test/dsh-preset.test.js',
    'test/dsh-preset-bundle.test.js',
    'test/mcp-client-matrix.test.js',
    'test/mcp-state-command.test.js',
    'test/tarball-install.test.js'
  ];

  const fast = scriptFiles('test:fast');
  const integration = scriptFiles('test:integration');
  const windowsCore = scriptFiles('test:windows:core');
  const buckets = [...fast, ...integration, ...windowsCore];
  const assigned = new Set(buckets);

  assert.deepEqual(
    windowsCore.filter((file) => !fast.includes(file) && !integration.includes(file)),
    WINDOWS_EXTRAS,
    'the Windows job must not shrink back to the two PR buckets'
  );
  // A renamed file leaves a dangling entry that nothing else reports.
  assert.deepEqual(
    buckets.filter((file) => !files.includes(file)),
    [],
    'every test suite named in an npm script must exist'
  );
  assert.deepEqual(
    [...POSIX_ONLY.keys()].filter((file) => !files.includes(file)),
    [],
    'every POSIX-only exemption must name a suite that exists'
  );
  assert.deepEqual(
    [...POSIX_ONLY.values()].filter((reason) => reason.trim().length === 0),
    [],
    'every POSIX-only exemption needs a reason'
  );
  assert.deepEqual(
    files.filter((file) => !assigned.has(file) && !POSIX_ONLY.has(file)),
    [],
    'assign each test suite to test:fast, test:integration or test:windows:core'
  );
  assert.deepEqual(
    [...POSIX_ONLY.keys()].filter((file) => assigned.has(file)),
    [],
    'a POSIX-only suite must not also claim a Windows bucket'
  );
  // A second patterned bucket would mean another set of cases silently dropped
  // out of the Windows PR path.
  assert.deepEqual(
    ['test:fast', 'test:integration', 'test:windows:core']
      .filter((script) => packageInfo.scripts[script].includes('--test-name-pattern')),
    ['test:integration'],
    'test:integration is the only bucket allowed to run a name-pattern subset'
  );
});
