import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { writeJsonAtomic } from './install-support.js';


export const KIMI_PLUGIN_ID = 'cowork-flow';

export function installedRegistryPath(home) {
  return join(home, 'plugins', 'installed.json');
}


// Same semantics as the host's own store (agent-core-v2's
// plugin/store.ts): an absent file reads as the empty
// registry, and anything the host itself would refuse to
// parse fails closed here too — merging into a file we do
// not understand would either drop other plugins or write
// back a shape the host rejects on load.
export async function readInstalledRegistry(home) {
  const filePath = installedRegistryPath(home);
  let text;
  try {
    text = await readFile(filePath, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return { version: 1, plugins: [] };
    throw error;
  }
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new Error(`${filePath} is not valid JSON (${error.message}); fix or remove it, then retry`);
  }
  if (typeof parsed !== 'object' || parsed === null || !Array.isArray(parsed.plugins)) {
    throw new Error(`${filePath} is not a Kimi Code plugin registry (expected {version, plugins: []}); fix or remove it, then retry`);
  }
  return parsed;
}


export async function writeInstalledRegistry(home, registry) {
  await writeJsonAtomic(installedRegistryPath(home), registry);
}


function isRecordEntry(entry) {
  return typeof entry === 'object' && entry !== null;
}


function sameEntryId(entry, id) {
  return isRecordEntry(entry) && String(entry.id ?? '').toLowerCase() === id;
}


// One record, merged the way the host merges its own install
// records (manager.ts::install): re-entering the registry
// keeps the user's enable state and the first install time,
// refreshes updatedAt, and rebuilds the field set from the
// host's persist() projection — which also drops stale
// github metadata a local-path install cannot back. Unknown
// top-level keys and every other plugin entry are preserved
// as read.
export async function upsertPluginRecord(home, record) {
  const registry = await readInstalledRegistry(home);
  const id = record.id.toLowerCase();
  const now = new Date().toISOString();
  const index = registry.plugins.findIndex((entry) => sameEntryId(entry, id));
  const existing = index >= 0 ? registry.plugins[index] : undefined;
  const next = {
    id,
    root: record.root,
    source: record.source,
    enabled: existing?.enabled ?? record.enabled,
    installedAt: existing?.installedAt ?? record.installedAt ?? now,
    updatedAt: now,
    originalSource: record.originalSource,
    ...(existing?.capabilities === undefined ? {} : { capabilities: existing.capabilities })
  };
  const plugins = [...registry.plugins];
  if (index >= 0) plugins[index] = next;
  else plugins.push(next);
  await writeInstalledRegistry(home, { ...registry, version: registry.version ?? 1, plugins });
  return next;
}


// The uninstall mirror: only the named record is dropped;
// every other entry and unknown top-level key survives.
// Returns false (and writes nothing) when the registry holds
// no such record.
export async function removePluginRecord(home, id) {
  const registry = await readInstalledRegistry(home);
  const key = id.toLowerCase();
  const plugins = registry.plugins.filter((entry) => !sameEntryId(entry, key));
  if (plugins.length === registry.plugins.length) return false;
  await writeInstalledRegistry(home, { ...registry, version: registry.version ?? 1, plugins });
  return true;
}
