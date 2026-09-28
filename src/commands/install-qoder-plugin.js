import { cp, mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const QODER_MARKETPLACE = 'cowork-flow-local';
const PLUGIN_NAME = 'cowork-flow';
const PLUGIN_KEY = `${PLUGIN_NAME}@${QODER_MARKETPLACE}`;
const REGISTRY_FILE = 'installed_plugins_v2.json';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function qoderHome() {
  const configured = (process.env.QODER_CONFIG_DIR || '').trim();
  return configured || join(homedir(), '.qoder');
}

function pluginPaths(home, version) {
  const pluginsRoot = join(home, 'plugins');
  const cacheRoot = join(pluginsRoot, 'cache', QODER_MARKETPLACE, PLUGIN_NAME);
  return {
    pluginsRoot,
    cacheRoot,
    installPath: version ? join(cacheRoot, version) : null,
    registry: join(pluginsRoot, REGISTRY_FILE),
    settings: join(home, 'settings.json')
  };
}

function invalidConfig(path, reason) {
  return new Error(`Invalid Qoder configuration at ${path}: ${reason}; file was left unchanged`);
}

async function readJsonObject(path, label) {
  let raw;
  try {
    raw = await readFile(path, 'utf8');
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return { exists: false, data: {} };
    }
    throw new Error(`Unable to read Qoder ${label} at ${path}; file was left unchanged: ${error.message}`);
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (error) {
    throw invalidConfig(path, error.message);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw invalidConfig(path, 'expected a JSON object');
  }
  return { exists: true, data };
}

async function loadConfigs(paths) {
  const registryDocument = await readJsonObject(paths.registry, 'plugin registry');
  const settingsDocument = await readJsonObject(paths.settings, 'settings');
  const registry = registryDocument.data;
  const settings = settingsDocument.data;
  if (!registry.plugins || typeof registry.plugins !== 'object' || Array.isArray(registry.plugins)) {
    if (Object.hasOwn(registry, 'plugins')) {
      throw invalidConfig(paths.registry, 'plugins must be an object');
    }
    registry.plugins = {};
  }
  if (Object.hasOwn(registry.plugins, PLUGIN_KEY) && !Array.isArray(registry.plugins[PLUGIN_KEY])) {
    throw invalidConfig(paths.registry, `plugins[${PLUGIN_KEY}] must be an array`);
  }
  if (Object.hasOwn(settings, 'enabledPlugins')) {
    if (!settings.enabledPlugins || typeof settings.enabledPlugins !== 'object' || Array.isArray(settings.enabledPlugins)) {
      throw invalidConfig(paths.settings, 'enabledPlugins must be an object');
    }
  } else {
    settings.enabledPlugins = {};
  }
  return { registry, settings };
}

// The Qoder plugin registry is not part of the published
// docs, so every write keeps unknown keys and unrelated
// entries verbatim: cowork-flow may only own its own key
// inside a file it did not create.
async function writeJsonAtomic(path, data) {
  await mkdir(dirname(path), { recursive: true });
  const temp = `${path}.cowork-flow.tmp`;
  await writeFile(temp, JSON.stringify(data, null, 2) + '\n', 'utf8');
  await rename(temp, path);
}

function registryEntry(existing, installPath, version, now) {
  const previous = Array.isArray(existing) ? existing[0] : null;
  return {
    scope: 'user',
    installPath,
    version,
    installedAt: previous?.installedAt || now,
    lastUpdated: now,
    userVisible: true
  };
}

async function updateRegistry(registry, paths, version, now, dryRun) {
  const entries = registry.plugins[PLUGIN_KEY] ?? [];
  registry.plugins[PLUGIN_KEY] = [
    registryEntry(entries, paths.installPath, version, now),
    ...entries.slice(1)
  ];

  if (dryRun) {
    console.log(`  Registry entry: ${paths.registry} -> ${PLUGIN_KEY}@${version}`);
    return;
  }
  await writeJsonAtomic(paths.registry, registry);
}

async function enablePlugin(settings, paths, dryRun) {
  settings.enabledPlugins[PLUGIN_KEY] = true;

  if (dryRun) {
    console.log(`  Enabled flag: ${paths.settings} -> enabledPlugins["${PLUGIN_KEY}"]=true`);
    return;
  }
  await writeJsonAtomic(paths.settings, settings);
}

async function uninstall(paths, dryRun) {
  const { registry, settings } = await loadConfigs(paths);
  const owned = registry.plugins[PLUGIN_KEY];
  if (dryRun) {
    console.log(`[dry-run] Would remove ${PLUGIN_KEY} from ${paths.registry}`);
    console.log(`[dry-run] Would remove ${paths.cacheRoot}`);
    return 0;
  }
  if (owned) {
    delete registry.plugins[PLUGIN_KEY];
    await writeJsonAtomic(paths.registry, registry);
  }
  if (PLUGIN_KEY in settings.enabledPlugins) {
    delete settings.enabledPlugins[PLUGIN_KEY];
    await writeJsonAtomic(paths.settings, settings);
  }
  await rm(paths.cacheRoot, { recursive: true, force: true });
  console.log(
    owned
      ? `✓ cowork-flow Qoder plugin uninstalled (${PLUGIN_KEY})`
      : `cowork-flow Qoder plugin was not registered; removed any cached copy at ${paths.cacheRoot}`
  );
  return 0;
}

export async function runInstallQoderPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = qoderHome();
  const { version } = await readPackageInfo();
  const target = pluginPaths(home, version);

  if (remove) {
    return uninstall(target, dryRun);
  }

  const { sourceDir: pluginSrc, manifest } = pluginPayload('qoder');
  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Qoder plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  const configs = await loadConfigs(target);
  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Qoder plugin:`);
  console.log(`  Plugin: ${pluginSrc} -> ${target.installPath}`);

  const registeredEntries = configs.registry.plugins[PLUGIN_KEY];
  const pluginRegistered = Array.isArray(registeredEntries) && registeredEntries.length > 0;
  const pluginEnabled = configs.settings.enabledPlugins[PLUGIN_KEY] === true;
  if (
    !dryRun &&
    (await pathExists(target.installPath)) &&
    !force &&
    pluginRegistered &&
    pluginEnabled
  ) {
    console.log(`cowork-flow Qoder plugin already installed at ${target.installPath}`);
    console.log('Use --force to overwrite.');
    return 0;
  }

  const now = new Date().toISOString();
  if (dryRun) {
    await updateRegistry(configs.registry, target, version, now, true);
    await enablePlugin(configs.settings, target, true);
    return 0;
  }

  await mkdir(target.cacheRoot, { recursive: true });
  await rm(target.installPath, { recursive: true, force: true });
  await cp(pluginSrc, target.installPath, { recursive: true });
  await stampPayloadManifest(target.installPath, manifest, version);
  // Registry and enable flag come last: a half-copied
  // payload must never be advertised as installed.
  await updateRegistry(configs.registry, target, version, now, false);
  await enablePlugin(configs.settings, target, false);

  console.log(`✓ cowork-flow Qoder plugin installed to ${target.installPath}`);
  console.log('  Restart Qoder to load the plugin (the IDE has no hook hot reload).');
  return 0;
}
