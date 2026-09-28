import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { cp, mkdir, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { readPluginMetadata } from '../lib/plugin-metadata.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const MARKETPLACE_NAME = 'cowork-flow-local';
const PLUGIN_NAME = 'cowork-flow';
const PLUGIN_KEY = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
const MARKETPLACE_MANIFEST = join('.agents', 'plugins', 'marketplace.json');

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


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

// codex validates marketplace entries: each plugin entry
// carries an explicit installation/authentication policy
// and a category, and the display name lives in the
// top-level interface object (codex plugin authoring
// guide, verified against official instances).
function marketplaceManifest(metadata) {
  return {
    name: MARKETPLACE_NAME,
    interface: { displayName: `${metadata.displayName} (local)` },
    plugins: [
      {
        name: PLUGIN_NAME,
        source: { source: 'local', path: `./plugins/${PLUGIN_NAME}` },
        policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
        category: metadata.category
      }
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

// COWORK_FLOW_CODEX is authoritative: falling back to
// another CLI would make a mistyped path silently install
// elsewhere.
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

// Node refuses to spawn .cmd/.bat without a shell, and
// shell mode joins the command with spaces without
// escaping, so a token with a space (a profile path, a
// CODEX_HOME under one) would reach cmd.exe as two words.
// Real executables never go through a shell.
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

// Codex records its own canonical spelling of the source
// root (`\\?\C:\...`, forward slashes, trailing separator,
// casing), so raw string comparison would report a
// conflict for a registration that points exactly where we
// install.
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

// The CLI owns ~/.codex/config.toml: registration and
// enablement are its state, so cowork-flow writes the
// marketplace source and lets codex record it. A
// hand-written config.toml would also be unrecoverable for
// the user if the format shifts.
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

// codex references the marketplace root in place (no
// copy), so it has to stay where it is across upgrades;
// the payload is rewritten and the manifest written last,
// so a half-copied plugin is never discoverable.
async function materializeMarketplace({ home, pluginSrc, manifest, version, metadata }) {
  const root = marketplaceRoot(home);
  const target = pluginTarget(home);
  await mkdir(dirname(join(root, MARKETPLACE_MANIFEST)), { recursive: true });
  await rm(target, { recursive: true, force: true });
  await cp(pluginSrc, target, { recursive: true });
  await stampPayloadManifest(target, manifest, version);
  await writeFile(
    join(root, MARKETPLACE_MANIFEST),
    JSON.stringify(marketplaceManifest(metadata), null, 2) + '\n',
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

  let cliFailed = false;
  if (cli) {
    const pluginResult = runCodex(cli, ['plugin', 'remove', PLUGIN_KEY]);
    if (pluginResult.status !== 0) {
      console.log(`  plugin remove: ${failureOutput(pluginResult)}`);
      cliFailed = true;
    }
    const marketplaceResult = runCodex(cli, ['plugin', 'marketplace', 'remove', MARKETPLACE_NAME]);
    if (marketplaceResult.status !== 0) {
      console.log(`  marketplace remove: ${failureOutput(marketplaceResult)}`);
      cliFailed = true;
    }
  } else {
    manualInstructions(root, { uninstall: true });
  }

  if (cliFailed) {
    console.log(`  retry: codex plugin remove ${PLUGIN_KEY}`);
    console.log(`  retry: codex plugin marketplace remove ${MARKETPLACE_NAME}`);
    console.log('Codex unregister did not complete; marketplace and cache were kept for retry.');
    return 1;
  }

  await rm(root, { recursive: true, force: true });
  await rm(cacheRoot(home), { recursive: true, force: true });
  if (!cli) {
    console.log('Codex uninstall requires manual follow-up; automatic cleanup was not fully confirmed.');
    return 1;
  }
  console.log(`✓ cowork-flow Codex plugin uninstalled (${PLUGIN_KEY})`);
  return 0;
}

export async function runInstallCodexPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = codexHome();
  const { version } = await readPackageInfo();
  const metadata = await readPluginMetadata();
  const cli = await findCodexCli(home);

  if (remove) {
    return uninstall({ home, cli, dryRun });
  }

  const { sourceDir: pluginSrc, manifest } = pluginPayload('codex');
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

  await materializeMarketplace({ home, pluginSrc, manifest, version, metadata });

  if (!cli) {
    manualInstructions(root);
    console.log('Codex install requires manual follow-up; the marketplace source is prepared but not registered.');
    return 1;
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
