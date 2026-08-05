import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { npmCommandOptions } from '../src/lib/package-info.js';
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
  assert.equal(files.has('template/.cowork-flow/scripts/adapters/cli/change.py'), true);
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
  assert.equal(files.has('template/.codex/config.toml'), true);
  assert.equal(files.has('template/.codex/hooks.json'), true);
  assert.equal(files.has('template/.codex/hooks/inject-workflow-state.py'), true);
  assert.equal(files.has('template/.claude/agents/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/commands/cowork-implement.md'), true);
  assert.equal(files.has('template/.claude/settings.json'), true);
  assert.equal(files.has('template/.claude/hooks/inject-workflow-state.py'), true);
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
  assert.match(packageInfo.scripts['test:all'], /npm run test:node:full/);
  assert.match(packageInfo.scripts['test:all'], /npm run test:template:full/);
  assert.match(packageInfo.scripts['test:all'], /npm run pack:check/);
  assert.equal(packageLock.version, packageInfo.version);
  assert.equal(packageLock.packages[''].version, packageInfo.version);
});
