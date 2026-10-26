import { realpath, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import {
  KIMI_PLUGIN_ID,
  installedRegistryPath,
  readInstalledRegistry,
  removePluginRecord,
  upsertPluginRecord
} from '../lib/kimi-installed-registry.js';
import { foreignTargetRefusal, installPayloadDir, uninstallPayloadDir } from '../lib/payload-install.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
const MANIFEST_MARKER = 'cowork-flow';
const LABEL = 'Kimi Code plugin';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function kimiHome(env = process.env) {
  const configured = (env.KIMI_CODE_HOME || '').trim();
  // The host rejects a relative plugin root; the resolved path is printed to paste.
  return configured ? resolve(configured) : join(homedir(), '.kimi-code');
}

// The stable reinstall source, kept for the registry's
// `originalSource` and for a user who still runs the host's
// own `/plugins install` by hand; deliberately NOT
// `plugins/managed/` (the host's copy carries its own
// lifecycle).
function sourceDir(home) {
  return join(home, 'plugins', 'sources', PLUGIN_NAME);
}

// The host's installed copy. On every start the host parses
// each registry record's manifest under this tree, so the
// record we write must point at a freshly stamped copy here
// — `sources/` alone is not loaded by anything.
function managedDir(home) {
  return join(home, 'plugins', 'managed', PLUGIN_NAME);
}


// The installed copy is read through the payload declaration's own manifest path.
async function ownsInstall(target, manifestRelative) {
  const manifest = await readJsonFile(join(target, ...manifestRelative.split('/')));
  return manifest?.name === MANIFEST_MARKER;
}


export async function runInstallKimiPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = kimiHome();
  const target = sourceDir(home);
  const managed = managedDir(home);
  const { sourceDir: pluginSrc, manifest } = pluginPayload('kimi-code');
  const { version } = await readPackageInfo();

  if (remove) {
    // Fail closed before any deletion, the mirror of the install path: a
    // merge into a registry we cannot read would drop the other plugins it
    // holds, so a deletion we cannot follow with a clean record removal must
    // not start.
    await readInstalledRegistry(home);

    await uninstallPayloadDir({
      target: managed, label: LABEL, dryRun, force,
      ownsInstall: () => ownsInstall(managed, manifest),
      refusal: () => foreignTargetRefusal({
        target: managed, probe: manifest, name: MANIFEST_MARKER, noun: 'directory'
      }),
      onPreview: () => {
        console.log(`[dry-run] Would remove ${managed}`);
      },
      remove: async () => {
        await rm(managed, { recursive: true, force: true });
        console.log(`✓ cowork-flow ${LABEL} removed (${managed})`);
      }
    });
    await uninstallPayloadDir({
      target, label: LABEL, dryRun, force,
      ownsInstall: () => ownsInstall(target, manifest),
      refusal: () => foreignTargetRefusal({
        target, probe: manifest, name: MANIFEST_MARKER, noun: 'directory'
      }),
      onPreview: () => {
        console.log(`[dry-run] Would remove ${target}`);
      },
      remove: async () => {
        await rm(target, { recursive: true, force: true });
        console.log(`✓ cowork-flow ${LABEL} removed (${target})`);
      }
    });

    if (dryRun) {
      console.log(`[dry-run] Would drop the ${KIMI_PLUGIN_ID} record from ${installedRegistryPath(home)}.`);
      return 0;
    }

    const dropped = await removePluginRecord(home, KIMI_PLUGIN_ID);
    console.log(dropped
      ? `  Registry record removed from ${installedRegistryPath(home)}.`
      : `  No ${KIMI_PLUGIN_ID} record in ${installedRegistryPath(home)}; nothing to drop.`);
    console.log('  Restart Kimi Code to drop the plugin from its list.');
    return 0;
  }

  // Fail closed before the first write: the host refuses a
  // registry it cannot parse, and merging into (or replacing)
  // one we cannot parse would drop the other plugins it holds.
  await readInstalledRegistry(home);

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Kimi Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  await installPayloadDir({
    target, source: pluginSrc, label: LABEL, sourceKind: 'Source', dryRun, force,
    ownsInstall: () => ownsInstall(target, manifest),
    onInstalled: () => stampPayloadManifest(target, manifest, version)
  });
  await installPayloadDir({
    target: managed, source: pluginSrc, label: LABEL, sourceKind: 'Managed copy', dryRun, force,
    ownsInstall: () => ownsInstall(managed, manifest),
    onInstalled: () => stampPayloadManifest(managed, manifest, version)
  });

  if (dryRun) {
    console.log(`[dry-run] Would register ${KIMI_PLUGIN_ID} in ${installedRegistryPath(home)} (enabled).`);
    return 0;
  }

  // The record mirrors what the host's own install writes for
  // a local directory; the host re-reads the managed copy on
  // every start and needs no further handshake.
  await upsertPluginRecord(home, {
    id: KIMI_PLUGIN_ID,
    root: await realpath(managed),
    source: 'local-path',
    enabled: true,
    originalSource: target
  });
  console.log(`  Registered in ${installedRegistryPath(home)} (enabled).`);
  console.log('  Restart Kimi Code to load the plugin.');
  return 0;
}


// Read-only installed-state facts for `host inspect`.
export async function inspectInstalledState({ env = process.env } = {}) {
  const home = kimiHome(env);
  const registry = installedRegistryPath(home);
  const data = await readJsonFile(registry);
  const entries = Array.isArray(data?.plugins) ? data.plugins : [];
  const record = entries.find(
    (entry) => entry && typeof entry === 'object' && entry.id === KIMI_PLUGIN_ID
  );
  if (!record) {
    return {
      status: 'missing',
      version: null,
      payloadPath: null,
      registeredSource: registry,
      enabled: null,
      reason: 'no registry record'
    };
  }
  const root = typeof record.root === 'string' && record.root
    ? record.root
    : managedDir(home);
  const enabled = record.enabled !== false;
  const { manifest } = pluginPayload('kimi-code');
  for (const relative of [manifest, 'skills/cowork-flow-bootstrap/SKILL.md']) {
    if (!(await pathExists(join(root, ...relative.split('/'))))) {
      return {
        status: 'broken',
        version: null,
        payloadPath: root,
        registeredSource: registry,
        enabled,
        reason: `missing ${relative}`
      };
    }
  }
  const payloadManifest = await readJsonFile(join(root, ...manifest.split('/')));
  const version = typeof payloadManifest?.version === 'string'
    ? payloadManifest.version
    : null;
  const sourceMissing = !(await pathExists(sourceDir(home)));
  return {
    status: 'installed',
    version,
    payloadPath: root,
    registeredSource: registry,
    enabled,
    reason: sourceMissing ? 'stable reinstall source directory is missing' : null
  };
}
