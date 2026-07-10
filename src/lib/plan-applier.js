import { createHash } from 'node:crypto';
import * as defaultFileSystem from 'node:fs/promises';
import { basename, dirname, join, resolve, sep } from 'node:path';

import { planActions } from './asset-plan.js';

const MATERIALIZED_ACTIONS = new Set(['create', 'update']);
const VERSION_PATH = '.cowork-flow/.version';
const TRANSACTION_STATUSES = new Set([
  'staging',
  'staged',
  'committing',
  'rolling-back',
  'rollback-failed',
  'committed'
]);

function sha256(content) {
  return createHash('sha256').update(content).digest('hex');
}

async function pathExists(fileSystem, path) {
  try {
    await fileSystem.access(path);
    return true;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

function transactionPrefix(targetDir) {
  return `.${basename(targetDir)}.cowork-flow-txn-`;
}

function transactionPath(root, section, relativePath) {
  return join(root, section, ...relativePath.split('/'));
}

async function writeMetadata(fileSystem, transactionRoot, metadata) {
  await fileSystem.writeFile(
    join(transactionRoot, 'transaction.json'),
    `${JSON.stringify(metadata, null, 2)}\n`,
    'utf8'
  );
}

async function stagePlan(plan, transactionRoot, metadata, fileSystem) {
  for (const [index, action] of plan.actions.entries()) {
    if (!MATERIALIZED_ACTIONS.has(action.action)) {
      continue;
    }
    const stagedPath = transactionPath(transactionRoot, 'staging', action.relativePath);
    await fileSystem.mkdir(dirname(stagedPath), { recursive: true });
    if (action.content !== undefined) {
      await fileSystem.writeFile(stagedPath, action.content, 'utf8');
    } else {
      await fileSystem.copyFile(action.source, stagedPath);
    }
    if (action.mode !== null) {
      await fileSystem.chmod(stagedPath, action.mode);
    }

    const stagedContent = await fileSystem.readFile(stagedPath, 'utf8');
    const stagedHash = sha256(stagedContent);
    if (stagedHash !== action.validation.sha256) {
      throw new Error(`Staged asset hash mismatch: ${action.relativePath}`);
    }
    if (action.validation.executable) {
      const stagedStats = await fileSystem.stat(stagedPath);
      if ((stagedStats.mode & 0o111) === 0) {
        throw new Error(`Staged executable lost permissions: ${action.relativePath}`);
      }
    }
    metadata.actions[index].staged = true;
  }
}

async function validateTargetState(action, fileSystem) {
  const exists = await pathExists(fileSystem, action.destination);
  if (action.targetPolicy === 'create' && exists) {
    throw new Error(`Target changed after planning: ${action.relativePath}`);
  }
  if (
    (action.targetPolicy === 'replace' || action.targetPolicy === 'delete')
    && action.targetExists
    && !exists
  ) {
    throw new Error(`Target disappeared after planning: ${action.relativePath}`);
  }
  return exists;
}

async function commitPlan(plan, transactionRoot, metadata, fileSystem) {
  metadata.status = 'committing';
  await writeMetadata(fileSystem, transactionRoot, metadata);

  for (const [index, action] of plan.actions.entries()) {
    if (action.action === 'skip' || action.action === 'protected') {
      continue;
    }

    const record = metadata.actions[index];
    const targetExists = await validateTargetState(action, fileSystem);
    const backupPath = transactionPath(transactionRoot, 'backup', action.relativePath);
    if (targetExists) {
      await fileSystem.mkdir(dirname(backupPath), { recursive: true });
      await fileSystem.rename(action.destination, backupPath);
      record.backedUp = true;
      await writeMetadata(fileSystem, transactionRoot, metadata);
    }

    if (action.action !== 'delete') {
      const stagedPath = transactionPath(transactionRoot, 'staging', action.relativePath);
      await fileSystem.mkdir(dirname(action.destination), { recursive: true });
      await fileSystem.rename(stagedPath, action.destination);
    }
    record.committed = true;
    await writeMetadata(fileSystem, transactionRoot, metadata);
  }
}

async function rollbackTransaction(transactionRoot, metadata, fileSystem) {
  let touched = false;
  for (let index = metadata.actions.length - 1; index >= 0; index -= 1) {
    const record = metadata.actions[index];
    const backupPath = transactionPath(transactionRoot, 'backup', record.relativePath);
    const stagedPath = transactionPath(transactionRoot, 'staging', record.relativePath);
    const backupExists = await pathExists(fileSystem, backupPath);
    const stagedExists = await pathExists(fileSystem, stagedPath);
    const destinationExists = await pathExists(fileSystem, record.destination);

    if (backupExists) {
      touched = true;
      if (destinationExists) {
        await fileSystem.rm(record.destination, { recursive: true, force: true });
      }
      await fileSystem.mkdir(dirname(record.destination), { recursive: true });
      await fileSystem.rename(backupPath, record.destination);
      continue;
    }

    const createdWasCommitted = record.committed
      || (record.targetPolicy === 'create' && !stagedExists && destinationExists);
    if (createdWasCommitted && destinationExists) {
      touched = true;
      await fileSystem.rm(record.destination, { recursive: true, force: true });
    }
  }

  if (!metadata.targetDirExisted && touched) {
    await fileSystem.rm(metadata.targetDir, { recursive: true, force: true });
  }
}

async function readMetadata(fileSystem, transactionRoot) {
  const metadataPath = join(transactionRoot, 'transaction.json');
  let content;
  try {
    content = await fileSystem.readFile(metadataPath, 'utf8');
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      throw new Error(
        `Asset transaction metadata is missing: ${metadataPath}`,
        { cause: error }
      );
    }
    throw error;
  }

  try {
    return JSON.parse(content);
  } catch (error) {
    if (error && error.name === 'SyntaxError') {
      throw new Error(
        `Asset transaction metadata is invalid: ${metadataPath}`,
        { cause: error }
      );
    }
    throw error;
  }
}

function validateMetadata(metadata, transactionRoot, resolvedTarget) {
  const metadataPath = join(transactionRoot, 'transaction.json');
  if (
    !metadata
    || typeof metadata !== 'object'
    || Array.isArray(metadata)
    || metadata.schemaVersion !== 1
    || typeof metadata.targetDir !== 'string'
    || typeof metadata.targetDirExisted !== 'boolean'
    || !TRANSACTION_STATUSES.has(metadata.status)
    || !Array.isArray(metadata.actions)
  ) {
    throw new Error(`Asset transaction metadata is invalid: ${metadataPath}`);
  }

  if (resolve(metadata.targetDir) !== resolvedTarget) {
    throw new Error(`Asset transaction target does not match: ${metadataPath}`);
  }

  const targetPrefix = `${resolvedTarget}${sep}`;
  for (const action of metadata.actions) {
    if (
      !action
      || typeof action !== 'object'
      || typeof action.relativePath !== 'string'
      || typeof action.destination !== 'string'
    ) {
      throw new Error(`Asset transaction metadata is invalid: ${metadataPath}`);
    }
    const destination = resolve(action.destination);
    const expectedDestination = resolve(
      resolvedTarget,
      ...action.relativePath.split('/')
    );
    if (
      destination !== expectedDestination
      || !destination.startsWith(targetPrefix)
    ) {
      throw new Error(`Asset transaction action escapes target: ${metadataPath}`);
    }
  }
}

export async function recoverAssetTransactions(
  targetDir,
  { fileSystem = defaultFileSystem } = {}
) {
  const resolvedTarget = resolve(targetDir);
  const parentDir = dirname(resolvedTarget);
  let entries;
  try {
    entries = await fileSystem.readdir(parentDir, { withFileTypes: true });
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return;
    }
    throw error;
  }

  const prefix = transactionPrefix(resolvedTarget);
  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.startsWith(prefix)) {
      continue;
    }
    const transactionRoot = join(parentDir, entry.name);
    const metadata = await readMetadata(fileSystem, transactionRoot);
    validateMetadata(metadata, transactionRoot, resolvedTarget);
    if (metadata.status !== 'committed') {
      await rollbackTransaction(transactionRoot, metadata, fileSystem);
    }
    await fileSystem.rm(transactionRoot, { recursive: true, force: true });
  }
}

export async function applyAssetPlan(
  plan,
  { dryRun = false, fileSystem = defaultFileSystem } = {}
) {
  if (dryRun) {
    return;
  }

  const actions = planActions(plan);
  if (!Array.isArray(actions) || !plan.targetDir) {
    throw new Error('Transactional asset apply requires a structured asset plan');
  }
  if (actions.at(-1)?.relativePath !== VERSION_PATH) {
    throw new Error('Asset plan must commit .cowork-flow/.version last');
  }

  await recoverAssetTransactions(plan.targetDir, { fileSystem });
  const parentDir = dirname(plan.targetDir);
  await fileSystem.mkdir(parentDir, { recursive: true });
  const transactionRoot = await fileSystem.mkdtemp(
    join(parentDir, transactionPrefix(plan.targetDir))
  );
  const metadata = {
    schemaVersion: 1,
    kind: plan.kind,
    status: 'staging',
    targetDir: plan.targetDir,
    targetDirExisted: await pathExists(fileSystem, plan.targetDir),
    actions: actions.map((action) => ({
      action: action.action,
      relativePath: action.relativePath,
      destination: action.destination,
      targetPolicy: action.targetPolicy,
      rollback: action.rollback,
      staged: false,
      backedUp: false,
      committed: false
    }))
  };

  try {
    await writeMetadata(fileSystem, transactionRoot, metadata);
    await stagePlan(plan, transactionRoot, metadata, fileSystem);
    metadata.status = 'staged';
    await writeMetadata(fileSystem, transactionRoot, metadata);
    await commitPlan(plan, transactionRoot, metadata, fileSystem);
    metadata.status = 'committed';
    await writeMetadata(fileSystem, transactionRoot, metadata);
    await fileSystem.rm(transactionRoot, { recursive: true, force: true });
  } catch (error) {
    try {
      metadata.status = 'rolling-back';
      await writeMetadata(fileSystem, transactionRoot, metadata);
      await rollbackTransaction(transactionRoot, metadata, fileSystem);
      await fileSystem.rm(transactionRoot, { recursive: true, force: true });
    } catch (rollbackError) {
      metadata.status = 'rollback-failed';
      try {
        await writeMetadata(fileSystem, transactionRoot, metadata);
      } catch {
        // Preserve the original and rollback failures below.
      }
      throw new AggregateError(
        [error, rollbackError],
        `Asset transaction rollback failed: ${plan.targetDir}`
      );
    }
    throw error;
  }
}
