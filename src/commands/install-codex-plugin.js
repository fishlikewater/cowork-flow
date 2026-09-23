import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { access, cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';

import { readPackageInfo } from '../lib/package-info.js';
import { packageRoot } from '../lib/paths.js';

const MARKETPLACE_NAME = 'cowork-flow-local';
const PLUGIN_NAME = 'cowork-flow';
const PLUGIN_KEY = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
const MARKETPLACE_MANIFEST = join('.agents', 'plugins', 'marketplace.json');

function parseArgs(args) {
  return {
    dryRun: args.includes('--dry-run'),
    force: args.includes('--force'),
    uninstall: args.includes('--uninstall')
  };
}

async function pathExists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

async function readJsonSafe(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch {
    return null;
  }
}

function codexHome() {
  const configured = (process.env.CODEX_HOME || '').trim();
  return configured || join(homedir(), '.codex');
}

function marketplaceRoot(home) {
  return join(home, 'plugins', 'marketplaces', MARKETPLACE_NAME);
}

function pluginTarget(home) {
  return join(marketplaceRoot(home), 'plugins', PLUGIN_NAME);
}

function cacheRoot(home) {
  return join(home, 'plugins', 'cache', MARKETPLACE_NAME, PLUGIN_NAME);
}

function marketplaceManifest() {
  return {
    name: MARKETPLACE_NAME,
    interface: { displayName: 'cowork-flow (local)' },
    plugins: [
      { name: PLUGIN_NAME, source: { source: 'local', path: `./plugins/${PLUGIN_NAME}` } }
    ]
  };
}

function whichCodex() {
  const extensions = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : [''];
  for (const dir of (process.env.PATH || '').split(delimiter)) {
    if (!dir) {
      continue;
    }
    for (const extension of extensions) {
      const candidate = join(dir, `codex${extension}`);
      if (existsSync(candidate)) {
        return candidate;
      }
    }
  }
  return null;
}

// An explicit override is authoritative: falling back to another CLI would make
// "COWORK_FLOW_CODEX=/missing/codex" silently install through a different one.
async function findCodexCli(home) {
  const configured = (process.env.COWORK_FLOW_CODEX || '').trim();
  if (configured) {
    return (await pathExists(configured)) ? configured : null;
  }
  const fromPath = whichCodex();
  if (fromPath) {
    return fromPath;
  }
  for (const candidate of [
    join(home, 'plugins', '.plugin-appserver', 'codex.exe'),
    join(home, 'plugins', '.plugin-appserver', 'codex')
  ]) {
    if (await pathExists(candidate)) {
      return candidate;
    }
  }
  return null;
}

// Node refuses to spawn .cmd/.bat without a shell, and shell mode joins the
// command with spaces without escaping anything, so a token that contains a
// space (a profile path like "C:\Users\Jane Doe\AppData\Roaming\npm\codex.cmd",
// or a CODEX_HOME under one) would reach cmd.exe as two words and fail. A real
// executable must not go through a shell at all.
function runCodex(cli, args) {
  if (!/\.(cmd|bat)$/i.test(cli)) {
    return spawnSync(cli, args, { encoding: 'utf8' });
  }
  const quote = (token) => (/\s/.test(token) ? `"${token}"` : token);
  return spawnSync([quote(cli), ...args.map(quote)].join(' '), {
    encoding: 'utf8',
    shell: true
  });
}

function parseJsonOutput(result) {
  try {
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

function failureOutput(result) {
  const output = `${result.stdout || ''}${result.stderr || ''}`.trim();
  return output || `exit ${result.status}`;
}

// Codex records its own canonical spelling of the source root, so the same
// directory can come back as `\\?\C:\...`, with forward slashes, a trailing
// separator, or different casing. Comparing the raw strings would report a
// conflict for a registration that points exactly where we install.
function sameRoot(left, right) {
  if (!left || !right) {
    return false;
  }
  const normalize = (value) => resolve(value).replace(/^\\\\\?\\/, '');
  const normalizedLeft = normalize(left);
  const normalizedRight = normalize(right);
  return process.platform === 'win32'
    ? normalizedLeft.toLowerCase() === normalizedRight.toLowerCase()
    : normalizedLeft === normalizedRight;
}

// The CLI owns ~/.codex/config.toml: registration and enablement are its state,
// so cowork-flow writes the marketplace source and lets codex record it. A
// hand-written config.toml would also be unrecoverable for the user if the
// format shifts.
function readCodexState(cli) {
  const marketplaces = parseJsonOutput(runCodex(cli, ['plugin', 'marketplace', 'list', '--json']));
  const plugins = parseJsonOutput(
    runCodex(cli, ['plugin', 'list', '--json', '-m', MARKETPLACE_NAME])
  );
  const registered = (marketplaces?.marketplaces || []).find(
    (marketplace) => marketplace.name === MARKETPLACE_NAME
  );
  const entry = (plugins?.installed || []).find((plugin) => plugin.pluginId === PLUGIN_KEY);
  return {
    registeredRoot: registered?.root || null,
    entry: entry || null
  };
}

async function stampManifest(target, version) {
  const manifestPath = join(target, '.codex-plugin', 'plugin.json');
  const manifest = await readJsonSafe(manifestPath);
  if (!manifest) {
    throw new Error(`Codex plugin manifest missing or unreadable: ${manifestPath}`);
  }
  manifest.version = version;
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
}

// The marketplace root is referenced in place by codex (no copy), so it has to
// stay where it is across upgrades; the payload is rewritten and the manifest
// goes last, so a half-copied plugin is never discoverable.
async function materializeMarketplace({ home, pluginSrc, version }) {
  const root = marketplaceRoot(home);
  const target = pluginTarget(home);
  await mkdir(dirname(join(root, MARKETPLACE_MANIFEST)), { recursive: true });
  await rm(target, { recursive: true, force: true });
  await cp(pluginSrc, target, { recursive: true });
  await stampManifest(target, version);
  await writeFile(
    join(root, MARKETPLACE_MANIFEST),
    JSON.stringify(marketplaceManifest(), null, 2) + '\n',
    'utf8'
  );
  return root;
}

function manualInstructions(root, { uninstall = false } = {}) {
  if (uninstall) {
    console.log('  codex CLI not found; unregister it manually with:');
    console.log(`    codex plugin remove ${PLUGIN_KEY}`);
    console.log(`    codex plugin marketplace remove ${MARKETPLACE_NAME}`);
  } else {
    console.log('  codex CLI not found; the marketplace source is ready, register it with:');
    console.log(`    codex plugin marketplace add ${root}`);
    console.log(`    codex plugin add ${PLUGIN_KEY}`);
  }
  console.log('  Set COWORK_FLOW_CODEX to the codex binary to let cowork-flow run these.');
}

async function uninstall({ home, cli, dryRun }) {
  const root = marketplaceRoot(home);
  if (dryRun) {
    console.log(`[dry-run] Would run: codex plugin remove ${PLUGIN_KEY}`);
    console.log(`[dry-run] Would run: codex plugin marketplace remove ${MARKETPLACE_NAME}`);
    console.log(`[dry-run] Would remove ${root}`);
    return 0;
  }

  if (cli) {
    const pluginResult = runCodex(cli, ['plugin', 'remove', PLUGIN_KEY]);
    if (pluginResult.status !== 0) {
      console.log(`  plugin remove: ${failureOutput(pluginResult)}`);
    }
    const marketplaceResult = runCodex(cli, ['plugin', 'marketplace', 'remove', MARKETPLACE_NAME]);
    if (marketplaceResult.status !== 0) {
      console.log(`  marketplace remove: ${failureOutput(marketplaceResult)}`);
    }
  } else {
    manualInstructions(root, { uninstall: true });
  }

  await rm(root, { recursive: true, force: true });
  await rm(cacheRoot(home), { recursive: true, force: true });
  console.log(`✓ cowork-flow Codex plugin uninstalled (${PLUGIN_KEY})`);
  return 0;
}

export async function runInstallCodexPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseArgs(args);
  const home = codexHome();
  const { version } = await readPackageInfo();
  const cli = await findCodexCli(home);

  if (remove) {
    return uninstall({ home, cli, dryRun });
  }

  const pluginSrc = join(packageRoot, 'presets', 'codex');
  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Codex plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  const root = marketplaceRoot(home);
  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Codex plugin:`);
  console.log(`  Marketplace: ${root}`);
  console.log(`  Plugin:      ${pluginSrc} -> ${pluginTarget(home)}`);
  console.log(`  Skills:      ${PLUGIN_NAME}/skills/cowork-flow-bootstrap (agents stay project-level)`);

  if (dryRun) {
    console.log(`[dry-run] Would run: codex plugin marketplace add ${root}`);
    console.log(`[dry-run] Would run: codex plugin add ${PLUGIN_KEY}`);
    return 0;
  }

  await materializeMarketplace({ home, pluginSrc, version });

  if (!cli) {
    manualInstructions(root);
    return 0;
  }

  const state = readCodexState(cli);
  if (!state.registeredRoot) {
    const addResult = runCodex(cli, ['plugin', 'marketplace', 'add', root]);
    if (addResult.status !== 0) {
      console.log(`  marketplace add failed: ${failureOutput(addResult)}`);
      return 1;
    }
  } else if (!sameRoot(state.registeredRoot, root)) {
    console.log(`  marketplace ${MARKETPLACE_NAME} is registered from ${state.registeredRoot}`);
    console.log(`  remove it first: codex plugin marketplace remove ${MARKETPLACE_NAME}`);
    return 1;
  }

  const installedVersion = state.entry?.installed ? state.entry.version : null;
  if (!force && installedVersion === version) {
    console.log(`cowork-flow Codex plugin already installed at ${cacheRoot(home)}`);
    console.log('  Re-run with --force to re-materialize it.');
    return 0;
  }

  const addResult = runCodex(cli, ['plugin', 'add', PLUGIN_KEY, '--json']);
  if (addResult.status !== 0) {
    console.log(`  plugin add failed: ${failureOutput(addResult)}`);
    return 1;
  }

  const added = parseJsonOutput(addResult);
  const after = readCodexState(cli);
  console.log(`✓ cowork-flow Codex plugin installed (${PLUGIN_KEY})`);
  if (added?.installedPath) {
    console.log(`  Payload: ${added.installedPath}`);
  }
  console.log(
    after.entry?.enabled
      ? '  Start a new Codex session to load the plugin Skills.'
      : `  Plugin is registered but not enabled; check codex plugin list for ${PLUGIN_KEY}.`
  );
  return 0;
}
