import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { cp, mkdir, readdir, rename, rm, symlink, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import {
  buildReadinessReport,
  buildSyncPlan,
  collectKeptRetirements,
  formatKeptRetirements
} from '../src/lib/copy-template.js';
import { templateRoot } from '../src/lib/paths.js';
import { createTempDir, exists, readText } from './helpers/fs.js';

// A retirement is only deleted when the target still matches what the template
// ships. Everything else — a modified file, a user's own addition, a Skill the
// template no longer carries, or a sync-protected path the framework never
// writes — must survive with a reported reason, because sync cannot prove the
// framework owns it.
const LIVE_SKILL = 'test-first';
// Four of the shipped Skills keep files in a subdirectory, so a flat Skill
// cannot stand in for the depth the ownership check has to walk.
const NESTED_SKILL = 'party-mode';
const RETIRED_SKILL = 'tdd';
const execFileAsync = promisify(execFile);
const CLI_BIN = fileURLToPath(new URL('../bin/cowork-flow.js', import.meta.url));
const MANIFEST_FIXTURES = new URL('../tests/fixtures/host-manifest/', import.meta.url);

async function runSyncWithManifestFixture(fixtureName, target) {
  const manifest = fileURLToPath(new URL(fixtureName, MANIFEST_FIXTURES));
  try {
    const result = await execFileAsync(process.execPath, [CLI_BIN, 'sync', target], {
      env: { ...process.env, COWORK_FLOW_HOST_ASSET_MANIFEST: manifest }
    });
    return { code: 0, stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    return { code: error.code, stdout: error.stdout ?? '', stderr: error.stderr ?? '' };
  }
}

async function createTarget(t) {
  const target = await createTempDir(t);
  await mkdir(join(target, '.cowork-flow'), { recursive: true });
  return target;
}

async function copySkillReplica(target, skill) {
  const replica = join(target, '.cowork-flow', 'skills', skill);
  await cp(join(templateRoot, 'skills', skill), replica, { recursive: true });
  return replica;
}

async function copyLegacyReplica(target) {
  return copySkillReplica(target, LIVE_SKILL);
}

async function plannedDeletions(target) {
  const plan = await buildSyncPlan(target, { platforms: ['codex'] });
  return plan.actions
    .filter((action) => action.action === 'delete')
    .map((action) => action.relativePath.replaceAll('\\', '/'));
}

function keptPairs(kept) {
  return kept.map((entry) => [entry.relativePath.replaceAll('\\', '/'), entry.reason]);
}

test('a byte-identical legacy Skill replica is retired', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);

  const deletions = await plannedDeletions(target);

  assert.ok(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), deletions.join(', '));
  // Planning is read-only: nothing is removed before the plan is applied.
  assert.equal(await exists(replica), true);
  assert.deepEqual(await collectKeptRetirements(target), []);
});

// Both ends of the file comparison get their own case: a replica is only
// verified when *every* file matches, so a check that stopped after the first
// (or the last) entry has to fail one of these.
test('a modified first file keeps the Skill replica', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await writeFile(join(replica, 'SKILL.md'), 'local edit\n', 'utf8');

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
  assert.equal(await readText(join(replica, 'SKILL.md')), 'local edit\n');
});

test('a modified last file keeps the Skill replica', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await writeFile(join(replica, 'manifest.json'), '{"local":true}\n', 'utf8');

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
});

test('an extra file inside a Skill directory keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await writeFile(join(replica, 'local-notes.md'), 'mine\n', 'utf8');

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
  assert.equal(await exists(join(replica, 'local-notes.md')), true);
});

// An empty directory holds no file, so a file-only comparison sees nothing
// added and would call the tree identical.
test('an extra empty directory inside a Skill keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await mkdir(join(replica, 'local-notes'), { recursive: true });

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
  assert.equal(await exists(join(replica, 'local-notes')), true);
});

test('an extra symlink inside a Skill keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  try {
    await symlink(join(replica, 'SKILL.md'), join(replica, 'skill-link.md'));
  } catch (error) {
    if (error && (error.code === 'EPERM' || error.code === 'EACCES')) {
      t.skip('creating symlinks needs a privilege this account does not hold');
      return;
    }
    throw error;
  }

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
});

// A file replaced by a symlink to identical bytes is still not the file the
// template shipped, so the entry kind has to be part of the comparison.
test('a Skill file replaced by a symlink keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await rm(join(replica, 'SKILL.md'));
  try {
    await symlink(join(templateRoot, 'skills', LIVE_SKILL, 'SKILL.md'), join(replica, 'SKILL.md'));
  } catch (error) {
    if (error && (error.code === 'EPERM' || error.code === 'EACCES')) {
      t.skip('creating symlinks needs a privilege this account does not hold');
      return;
    }
    throw error;
  }

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
});

// Same file count, different names: only an entry-by-entry comparison sees it.
test('a renamed file inside a Skill keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copyLegacyReplica(target);
  await rename(join(replica, 'manifest.json'), join(replica, 'manifest-local.json'));

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${LIVE_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${LIVE_SKILL}`, 'modified-or-extra']
  ]);
});

test('a byte-identical nested Skill replica is retired', async (t) => {
  const target = await createTarget(t);
  const replica = await copySkillReplica(target, NESTED_SKILL);

  const deletions = await plannedDeletions(target);

  // Retiring a Skill with subdirectories is the other half of the nested
  // walk: an entry comparison that never matches would keep it forever.
  assert.ok(deletions.includes(`.cowork-flow/skills/${NESTED_SKILL}`), deletions.join(', '));
  assert.equal(await exists(replica), true);
  assert.deepEqual(await collectKeptRetirements(target), []);
});

test('an extra file nested under a Skill subdirectory keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copySkillReplica(target, NESTED_SKILL);
  await writeFile(join(replica, 'scripts', 'local-only.py'), 'mine\n', 'utf8');

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${NESTED_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${NESTED_SKILL}`, 'modified-or-extra']
  ]);
});

test('an extra empty directory nested under a Skill subdirectory keeps the whole Skill', async (t) => {
  const target = await createTarget(t);
  const replica = await copySkillReplica(target, NESTED_SKILL);
  await mkdir(join(replica, 'scripts', 'local-notes'), { recursive: true });

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.cowork-flow/skills/${NESTED_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.cowork-flow/skills/${NESTED_SKILL}`, 'modified-or-extra']
  ]);
});

test('a Skill the template no longer carries is kept, not guessed away', async (t) => {
  const target = await createTarget(t);
  const retired = join(target, '.agents', 'skills', RETIRED_SKILL);
  await mkdir(retired, { recursive: true });
  await writeFile(join(retired, 'SKILL.md'), 'retired content\n', 'utf8');

  const deletions = await plannedDeletions(target);

  assert.equal(deletions.includes(`.agents/skills/${RETIRED_SKILL}`), false);
  assert.deepEqual(keptPairs(await collectKeptRetirements(target)), [
    [`.agents/skills/${RETIRED_SKILL}`, 'original-not-in-template']
  ]);
  assert.equal(await exists(retired), true);
});

// A sync-protected path is user-owned by contract: sync never writes it, so a
// retirement may not delete it either, however the file got there. The real
// manifest no longer protects a retired spec path, so the fixture declares one.
test('a sync-protected spec path is kept, not deleted', async (t) => {
  const target = await createTarget(t);
  const relative = '.cowork-flow/spec/backend/retired.md';
  const spec = join(target, relative);
  await mkdir(join(target, '.cowork-flow', 'spec', 'backend'), { recursive: true });
  await writeFile(join(target, '.cowork-flow', '.version'), '0.0.0\n', 'utf8');
  await writeFile(spec, '# Retired framework spec\n', 'utf8');

  const result = await runSyncWithManifestFixture('valid-protected-obsolete.json', target);

  assert.equal(result.code, 0, result.stderr);
  assert.match(result.stdout, /Kept \.cowork-flow\/spec\/backend\/retired\.md \(protected-path\)/);
  assert.equal(await readText(spec), '# Retired framework spec\n');
});

test('non-Skill obsolete files are still cleaned up', async (t) => {
  const target = await createTarget(t);
  const obsoleteFile = join(
    target,
    '.cowork-flow',
    'scripts',
    'common',
    'gates',
    'spec_validator.py'
  );
  await mkdir(join(target, '.cowork-flow', 'scripts', 'common', 'gates'), { recursive: true });
  await writeFile(obsoleteFile, 'retired validator\n', 'utf8');

  const deletions = await plannedDeletions(target);

  // Shortest-path-first: the removal may be the file itself or an ancestor.
  const obsoletePath = '.cowork-flow/scripts/common/gates/spec_validator.py';
  assert.ok(
    deletions.some((path) => path === obsoletePath || obsoletePath.startsWith(`${path}/`)),
    deletions.join(', ')
  );
  assert.deepEqual(await collectKeptRetirements(target), []);
});

test('the dry-run readiness report separates removals from retentions', async (t) => {
  const target = await createTarget(t);
  await copyLegacyReplica(target);
  const retired = join(target, '.agents', 'skills', RETIRED_SKILL);
  await mkdir(retired, { recursive: true });
  await writeFile(join(retired, 'SKILL.md'), 'retired content\n', 'utf8');

  const plan = await buildSyncPlan(target, { platforms: ['codex'] });
  const report = await buildReadinessReport(plan);

  assert.ok(
    report.wouldRemoveObsolete.some(
      (action) => action.path === `.cowork-flow/skills/${LIVE_SKILL}`
    ),
    JSON.stringify(report.wouldRemoveObsolete)
  );
  assert.deepEqual(
    report.wouldKeep.map((action) => [action.path, action.action, action.reason]),
    [[`.agents/skills/${RETIRED_SKILL}`, 'keep', 'original-not-in-template']]
  );
  // The report is a statement of intent: nothing was removed.
  assert.equal(await exists(retired), true);
  assert.equal(await exists(join(target, '.cowork-flow', 'skills', LIVE_SKILL)), true);
  assert.ok((await readdir(join(target, '.agents', 'skills'))).includes(RETIRED_SKILL));
});

test('the retention warning names every kept path and its reason', async (t) => {
  const target = await createTarget(t);
  await copyLegacyReplica(target);
  await writeFile(
    join(target, '.cowork-flow', 'skills', LIVE_SKILL, 'manifest.json'),
    '{"local":true}\n',
    'utf8'
  );
  const retired = join(target, '.agents', 'skills', RETIRED_SKILL);
  await mkdir(retired, { recursive: true });
  await writeFile(join(retired, 'SKILL.md'), 'retired content\n', 'utf8');

  const message = formatKeptRetirements(await collectKeptRetirements(target));

  assert.match(message, /^Kept 2 unverifiable retirement\(s\):\n/);
  assert.match(message, new RegExp(`Kept \\.cowork-flow/skills/${LIVE_SKILL} \\(modified-or-extra\\)`));
  assert.match(message, /Kept \.agents\/skills\/tdd \(original-not-in-template\)/);
});
