import { cp, mkdir, readFile, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile, writeJsonAtomic } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const QODER_MARKETPLACE = 'cowork-flow-local';
const PLUGIN_NAME = 'cowork-flow';
const PLUGIN_KEY = `${PLUGIN_NAME}@${QODER_MARKETPLACE}`;
const REGISTRY_FILE = 'installed_plugins_v2.json';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


// Qoder and Qoder CN share one plugin model and differ only in
// their user-level config home. The CN build keeps the project
// config directory at `.qoder`, so the project-level adapter stays
// single; only machine-level installs fan out.
const QODER_EDITIONS = [
  {
    variant: 'intl',
    configEnv: 'QODER_CONFIG_DIR',
    nameEnv: 'QODER_CONFIG_DIR_NAME',
    defaultName: '.qoder'
  },
  {
    variant: 'cn',
    configEnv: 'QODERCN_CONFIG_DIR',
    nameEnv: 'QODERCN_CONFIG_DIR_NAME',
    defaultName: '.qoder-cn'
  }
];


function editionLabel(variant) {
  return variant === 'cn' ? 'Qoder CN' : 'Qoder';
}


function qoderHomeForEdition(edition, env) {
  const configured = (env[edition.configEnv] || '').trim();
  if (configured) return configured;
  // The host lets the directory name be renamed; `*_CONFIG_DIR` is
  // the full-path override, `*_CONFIG_DIR_NAME` only the basename.
  const name = (env[edition.nameEnv] || '').trim() || edition.defaultName;
  return join(homedir(), name);
}


async function editionIsPresent(home) {
  return (
    (await pathExists(join(home, 'settings.json')))
    || (await pathExists(join(home, 'plugins')))
  );
}


// Install targets: an explicit config env is a single-target
// instruction and suppresses discovery; otherwise every edition with
// product state on disk is covered; a machine with no Qoder state yet
// keeps the historical `.qoder` default.
async function qoderHomes(env = process.env) {
  return await resolveQoderHomes(env, { includePresentWithExplicit: false });
}


// Inspect reports every edition that exists on the machine, plus an
// explicitly named home even when it does not exist yet. An install
// override must not hide another present edition from the doctor.
async function qoderInspectHomes(env = process.env) {
  return await resolveQoderHomes(env, { includePresentWithExplicit: true });
}


async function resolveQoderHomes(env, { includePresentWithExplicit }) {
  const editions = QODER_EDITIONS.map((edition) => ({
    edition,
    home: qoderHomeForEdition(edition, env),
    explicit: Boolean((env[edition.configEnv] || '').trim())
  }));
  const discovered = await Promise.all(
    editions.map(async (item) => ({
      ...item,
      present: await editionIsPresent(item.home)
    }))
  );
  let selected;
  if (includePresentWithExplicit) {
    selected = discovered.filter((item) => item.explicit || item.present);
  } else {
    const explicit = discovered.filter((item) => item.explicit);
    selected = explicit.length > 0
      ? explicit
      : discovered.filter((item) => item.present);
  }
  const seen = new Set();
  const homes = [];
  for (const item of selected.length > 0 ? selected : [discovered[0]]) {
    const key = resolve(item.home);
    if (seen.has(key)) continue;
    seen.add(key);
    homes.push({ variant: item.edition.variant, home: item.home });
  }
  return homes;
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

function failureSummary(failures) {
  return failures
    .map(({ variant, home, error }) => `${editionLabel(variant)} (${home}): ${error.message}`)
    .join('; ');
}


async function uninstallQoderHome(paths, { variant, dryRun }) {
  const label = editionLabel(variant);
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
      ? `✓ cowork-flow ${label} plugin uninstalled (${PLUGIN_KEY})`
      : `cowork-flow ${label} plugin was not registered; removed any cached copy at ${paths.cacheRoot}`
  );
  return 0;
}


async function uninstallQoderEditions(homes, dryRun) {
  const failures = [];
  for (const { variant, home } of homes) {
    try {
      await uninstallQoderHome(pluginPaths(home, null), { variant, dryRun });
    } catch (error) {
      failures.push({ variant, home, error });
    }
  }
  if (failures.length > 0) {
    throw new Error(
      `Qoder plugin uninstall failed for ${failures.length} edition(s): ${failureSummary(failures)}`
    );
  }
  return 0;
}

async function installQoderHome(target, { version, pluginSrc, manifest, force, variant, dryRun }) {
  const label = editionLabel(variant);
  const configs = await loadConfigs(target);
  console.log(`  ${label}: ${pluginSrc} -> ${target.installPath}`);

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
    console.log(`cowork-flow ${label} plugin already installed at ${target.installPath}`);
    console.log('Use --force to overwrite.');
    return;
  }

  const now = new Date().toISOString();
  if (dryRun) {
    await updateRegistry(configs.registry, target, version, now, true);
    await enablePlugin(configs.settings, target, true);
    return;
  }

  await mkdir(target.cacheRoot, { recursive: true });
  await rm(target.installPath, { recursive: true, force: true });
  await cp(pluginSrc, target.installPath, { recursive: true });
  await stampPayloadManifest(target.installPath, manifest, version);
  // Registry and enable flag come last: a half-copied
  // payload must never be advertised as installed.
  await updateRegistry(configs.registry, target, version, now, false);
  await enablePlugin(configs.settings, target, false);

  console.log(`✓ cowork-flow ${label} plugin installed to ${target.installPath}`);
}


export async function runInstallQoderPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const homes = await qoderHomes();
  if (remove) {
    return await uninstallQoderEditions(homes, dryRun);
  }

  const { version } = await readPackageInfo();
  const { sourceDir: pluginSrc, manifest } = pluginPayload('qoder');
  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Qoder plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Qoder plugin:`);
  const failures = [];
  for (const { variant, home } of homes) {
    try {
      await installQoderHome(pluginPaths(home, version), {
        version,
        pluginSrc,
        manifest,
        force,
        variant,
        dryRun
      });
    } catch (error) {
      failures.push({ variant, home, error });
    }
  }
  if (failures.length > 0) {
    throw new Error(
      `Qoder plugin install failed for ${failures.length} edition(s): ${failureSummary(failures)}`
    );
  }
  if (!dryRun) {
    console.log('  Restart Qoder to load the plugin (the IDE has no hook hot reload).');
  }
  return 0;
}


// Read-only installed-state facts for `host inspect`. The registry and the
// settings flag are the host's records; the payload files are what a session
// actually loads. One facts object per present edition.
export async function inspectInstalledState({ env = process.env } = {}) {
  const homes = await qoderInspectHomes(env);
  return await Promise.all(
    homes.map(async ({ variant, home }) => ({
      ...(await inspectQoderHome(home)),
      variant
    }))
  );
}


async function inspectQoderHome(home) {
  const paths = pluginPaths(home, null);
  const registry = await readJsonFile(paths.registry);
  const entries = registry?.plugins?.[PLUGIN_KEY];
  const entry = Array.isArray(entries) ? entries[0] : null;
  if (!entry || typeof entry !== 'object') {
    return {
      status: 'missing',
      version: null,
      payloadPath: null,
      detailPath: paths.registry,
      registeredSource: paths.registry,
      enabled: null,
      reason: 'no registry entry'
    };
  }
  const version = typeof entry.version === 'string' ? entry.version : null;
  const installPath = typeof entry.installPath === 'string' ? entry.installPath : '';
  if (!installPath) {
    return {
      status: 'broken',
      version,
      payloadPath: null,
      detailPath: paths.registry,
      registeredSource: paths.registry,
      enabled: null,
      reason: 'registry entry has no installPath'
    };
  }
  const { manifest } = pluginPayload('qoder');
  for (const relative of [manifest, 'hooks/hooks.json', 'hooks/inject-context.mjs']) {
    if (!(await pathExists(join(installPath, ...relative.split('/'))))) {
      const role = relative === manifest ? 'payload manifest' : 'required file';
      return {
        status: 'broken',
        version,
        payloadPath: installPath,
        detailPath: join(installPath, ...relative.split('/')),
        registeredSource: paths.registry,
        enabled: null,
        reason: `missing ${relative} (${role})`
      };
    }
  }
  const settings = await readJsonFile(paths.settings);
  const enabled = settings?.enabledPlugins?.[PLUGIN_KEY] === true;
  return {
    status: 'installed',
    version,
    payloadPath: installPath,
    detailPath: enabled
      ? join(installPath, ...manifest.split('/'))
      : paths.settings,
    registeredSource: paths.registry,
    enabled,
    reason: enabled ? null : 'enable flag is not true'
  };
}
