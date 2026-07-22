import assert from 'node:assert/strict';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import { dirname, join, sep } from 'node:path';
import { test } from 'node:test';

import { createAssetPlan } from '../src/lib/asset-plan.js';
import {
  applyAssetPlan,
  recoverAssetTransactions
} from '../src/lib/plan-applier.js';
import {
  createTempDir,
  fileSystemWithRenameFailure,
  readText
} from './helpers/fs.js';

test('asset plan is immutable and keeps the version action last', async (t) => {
  const root = await createTempDir(t);
  const source = join(root, 'source.txt');
  const target = join(root, 'target');
  await writeFile(source, 'new content\n', 'utf8');

  const plan = await createAssetPlan({
    kind: 'sync',
    targetDir: target,
    actions: [
      {
        action: 'update',
        source,
        destination: join(target, 'alpha.txt'),
        relativePath: 'alpha.txt',
        targetExists: true
      },
      {
        action: 'update',
        source: null,
        destination: join(target, '.cowork-flow', '.version'),
        relativePath: '.cowork-flow/.version',
        content: '1.2.3\n',
        targetExists: true
      },
      {
        action: 'delete',
        source: null,
        destination: join(target, 'obsolete.txt'),
        relativePath: 'obsolete.txt'
      }
    ]
  });

  const alphaAction = plan.actions.find((action) => action.relativePath === 'alpha.txt');
  const deleteAction = plan.actions.find((action) => action.relativePath === 'obsolete.txt');
  const versionAction = plan.actions.find(
    (action) => action.relativePath === '.cowork-flow/.version'
  );
  assert.equal(Object.isFrozen(plan), true);
  assert.equal(Object.isFrozen(plan.actions), true);
  assert.equal(Object.isFrozen(plan.actions[0]), true);
  assert.equal(plan.actions.at(-1).relativePath, '.cowork-flow/.version');
  assert.match(alphaAction.sourceHash, /^[a-f0-9]{64}$/);
  assert.equal(alphaAction.validation.sha256, alphaAction.sourceHash);
  assert.equal(alphaAction.rollback.strategy, 'restore-backup');
  assert.equal(deleteAction.targetExists, true);
  assert.equal(deleteAction.rollback.strategy, 'restore-backup');
  assert.equal(versionAction.targetPolicy, 'replace');
});

test('staging hash validation fails before target mutation', async (t) => {
  const root = await createTempDir(t);
  const target = join(root, 'target');
  const source = join(root, 'source.txt');
  const destination = join(target, 'alpha.txt');
  const versionFile = join(target, '.cowork-flow', '.version');
  await mkdir(dirname(versionFile), { recursive: true });
  await writeFile(source, 'planned content\n', 'utf8');
  await writeFile(destination, 'old content\n', 'utf8');
  await writeFile(versionFile, '0.1.0\n', 'utf8');

  const plan = await createAssetPlan({
    kind: 'sync',
    targetDir: target,
    actions: [
      {
        action: 'update',
        source,
        destination,
        relativePath: 'alpha.txt',
        targetExists: true
      },
      {
        action: 'update',
        source: null,
        destination: versionFile,
        relativePath: '.cowork-flow/.version',
        content: '1.2.3\n',
        targetExists: true
      }
    ]
  });
  await writeFile(source, 'tampered after planning\n', 'utf8');

  await assert.rejects(applyAssetPlan(plan), /Staged asset hash mismatch/);
  assert.equal(await readText(destination), 'old content\n');
  assert.equal(await readText(versionFile), '0.1.0\n');
});

test('the next apply can recover a rollback-failed transaction', async (t) => {
  const root = await createTempDir(t);
  const target = join(root, 'target');
  const source = join(root, 'source.txt');
  const destination = join(target, 'alpha.txt');
  const versionFile = join(target, '.cowork-flow', '.version');
  await mkdir(dirname(versionFile), { recursive: true });
  await writeFile(source, 'new content\n', 'utf8');
  await writeFile(destination, 'old content\n', 'utf8');
  await writeFile(versionFile, '0.1.0\n', 'utf8');

  const plan = await createAssetPlan({
    kind: 'sync',
    targetDir: target,
    actions: [
      {
        action: 'update',
        source,
        destination,
        relativePath: 'alpha.txt',
        targetExists: true
      },
      {
        action: 'update',
        source: null,
        destination: versionFile,
        relativePath: '.cowork-flow/.version',
        content: '1.2.3\n',
        targetExists: true
      }
    ]
  });
  const failingFileSystem = fileSystemWithRenameFailure(
    (sourcePath, destinationPath) => destinationPath === versionFile
      && (
        sourcePath.includes(`${sep}staging${sep}`)
        || sourcePath.includes(`${sep}backup${sep}`)
      )
  );

  await assert.rejects(
    applyAssetPlan(plan, { fileSystem: failingFileSystem }),
    /rollback failed/
  );
  await recoverAssetTransactions(target);

  assert.equal(await readText(destination), 'old content\n');
  assert.equal(await readText(versionFile), '0.1.0\n');
  const transactionDirs = (await readdir(root)).filter(
    (name) => name.startsWith('.target.cowork-flow-txn-')
  );
  assert.deepEqual(transactionDirs, []);
});

test('recovery fails closed when transaction metadata is corrupted', async (t) => {
  const root = await createTempDir(t);
  const target = join(root, 'target');
  const transactionRoot = join(root, '.target.cowork-flow-txn-corrupted');
  await mkdir(transactionRoot, { recursive: true });
  await writeFile(
    join(transactionRoot, 'transaction.json'),
    '{"status":"committing"',
    'utf8'
  );

  await assert.rejects(
    recoverAssetTransactions(target),
    /transaction metadata is invalid/i
  );
  assert.equal((await readdir(root)).includes('.target.cowork-flow-txn-corrupted'), true);
});
