import { createHash } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';

const VERSION_PATH = '.cowork-flow/.version';
const MATERIALIZED_ACTIONS = new Set(['create', 'update']);

function sha256(content) {
  return createHash('sha256').update(content).digest('hex');
}

function normalizeRelativePath(value) {
  const normalized = String(value).replaceAll('\\', '/');
  if (
    normalized.startsWith('/')
    || normalized === '..'
    || normalized.startsWith('../')
    || normalized.includes('/../')
  ) {
    throw new Error(`Asset plan path must stay inside the target: ${value}`);
  }
  return normalized;
}

function targetPolicy(action) {
  if (action === 'create') return 'create';
  if (action === 'update') return 'replace';
  if (action === 'delete') return 'delete';
  return 'preserve';
}

function rollbackStrategy(action, targetExists) {
  if (action === 'skip' || action === 'protected') return 'none';
  if (targetExists || action === 'update' || action === 'delete') {
    return 'restore-backup';
  }
  return 'remove-created';
}

async function readMode(action) {
  try {
    const path = action.source ?? action.destination;
    if (!path) return null;
    const stats = await stat(path);
    return stats.mode & 0o777;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function enrichAction(rawAction) {
  const relativePath = normalizeRelativePath(rawAction.relativePath);
  const action = rawAction.action;
  const targetExists = rawAction.targetExists
    ?? (action === 'update' || action === 'delete');
  let content = null;
  let mode = rawAction.mode ?? null;

  if (MATERIALIZED_ACTIONS.has(action)) {
    if (rawAction.content !== undefined) {
      content = Buffer.from(rawAction.content, 'utf8');
      if (mode === null && targetExists) {
        mode = await readMode(rawAction);
      }
    } else {
      content = await readFile(rawAction.source, 'utf8');
      if (mode === null) {
        mode = await readMode(rawAction);
      }
    }
  }

  const sourceHash = content === null ? null : sha256(content);
  const enriched = {
    ...rawAction,
    relativePath,
    targetExists: Boolean(targetExists),
    sourceHash,
    mode,
    targetPolicy: targetPolicy(action),
    validation: {
      sha256: sourceHash,
      executable: mode !== null && (mode & 0o111) !== 0
    },
    rollback: {
      strategy: rollbackStrategy(action, Boolean(targetExists))
    }
  };
  return deepFreeze(enriched);
}

function actionOrder(left, right) {
  const leftVersion = left.relativePath === VERSION_PATH;
  const rightVersion = right.relativePath === VERSION_PATH;
  if (leftVersion !== rightVersion) {
    return leftVersion ? 1 : -1;
  }
  return left.relativePath.localeCompare(right.relativePath);
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) {
    return value;
  }
  for (const child of Object.values(value)) {
    deepFreeze(child);
  }
  return Object.freeze(value);
}

export function planActions(planOrActions) {
  return Array.isArray(planOrActions) ? planOrActions : planOrActions.actions;
}

export async function createAssetPlan({ kind, targetDir, actions }) {
  const enriched = await Promise.all(actions.map(enrichAction));
  enriched.sort(actionOrder);
  return deepFreeze({
    schemaVersion: 1,
    kind,
    targetDir: resolve(targetDir),
    actions: enriched
  });
}
