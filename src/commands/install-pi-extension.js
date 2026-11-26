import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

import { parseInstallArgs } from '../lib/install-support.js';
import { pruneEmptyDir } from '../lib/payload-install.js';
import { templateRoot } from '../lib/paths.js';

const LABEL = 'Pi extension';
// Pi discovers `extensions/*.ts` one level deep inside the agent directory.
const EXTENSION_RELATIVE = ['extensions', 'cowork-flow.ts'];
const EXTENSION_DIR_RELATIVE = ['extensions'];
// The ownership signal the installer and the inspector both read.
const MARKER = 'CoworkFlowPiExtension';
// The packaged source doubles as the install payload; the project copy is
// never synced, so this is the only place the file is read from.
const SOURCE = join(templateRoot, '.pi', 'extensions', 'cowork-flow.ts');

// Rendered by `host add`/`host remove`; the installer's own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


// `$PI_CODING_AGENT_DIR` is Pi's documented config-dir override; the default
// is `~/.pi/agent` on every platform.
export function piAgentDir(env = process.env) {
  const configured = (env.PI_CODING_AGENT_DIR || '').trim();
  return configured || join(homedir(), '.pi', 'agent');
}

const extensionPath = (home) => join(home, ...EXTENSION_RELATIVE);


async function readIfExists(path) {
  try {
    return await readFile(path, 'utf8');
  } catch {
    return null;
  }
}


function ownsInstall(installed) {
  return typeof installed === 'string' && installed.includes(MARKER);
}


export async function runInstallPiExtension(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = piAgentDir();
  const target = extensionPath(home);

  if (remove) {
    const installed = await readIfExists(target);
    if (installed === null) {
      console.log(`[SKIP] ${LABEL} is not installed at ${target}`);
      return;
    }
    if (!ownsInstall(installed) && !force) {
      throw new Error(
        `${target} exists but does not look like the cowork-flow Pi extension (no ${MARKER} in it). `
        + 'Refusing to delete a file this installer did not create; use --force to remove it anyway.'
      );
    }
    if (dryRun) {
      console.log(`[dry-run] Would remove ${target}`);
      return;
    }
    await rm(target, { force: true });
    const cleaned = await pruneEmptyDir(join(home, ...EXTENSION_DIR_RELATIVE));
    console.log(`✓ cowork-flow ${LABEL} uninstalled (removed ${target})`);
    if (cleaned) console.log(`  Removed the now-empty ${join(home, ...EXTENSION_DIR_RELATIVE)}`);
    console.log('  Restart Pi to drop the extension.');
    return;
  }

  const source = await readIfExists(SOURCE);
  if (source === null) {
    throw new Error(`Pi extension source missing at ${SOURCE}. Reinstall cowork-flow.`);
  }
  const installed = await readIfExists(target);
  if (installed !== null && !ownsInstall(installed) && !force) {
    throw new Error(
      `${target} exists but does not look like the cowork-flow Pi extension (no ${MARKER} in it). `
      + 'Refusing to overwrite a file this installer did not create; use --force to replace it anyway.'
    );
  }
  if (installed === source) {
    console.log(`✓ cowork-flow ${LABEL} already installed at ${target}`);
    return;
  }
  if (dryRun) {
    console.log(`[dry-run] Would write ${target}`);
    console.log(`  Injects the workflow state rendered by .cowork-flow/scripts/adapters/host/inject.py --host pi`);
    return;
  }
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, source, 'utf8');
  console.log(`✓ cowork-flow ${LABEL} installed at ${target}`);
  console.log('  Loads in the next Pi session; no registry or enable step.');
}


// Read-only installed-state facts for `host inspect`. Pi extensions carry no
// version manifest, so version stays null and the content comparison decides
// staleness against the packaged source.
export async function inspectInstalledState({ env = process.env } = {}) {
  const home = piAgentDir(env);
  const target = extensionPath(home);
  const installed = await readIfExists(target);
  if (installed === null) {
    return {
      status: 'missing',
      version: null,
      payloadPath: home,
      detailPath: target,
      registeredSource: target,
      enabled: null,
      reason: 'no extension file'
    };
  }
  if (!ownsInstall(installed)) {
    return {
      status: 'missing',
      version: null,
      payloadPath: home,
      detailPath: target,
      registeredSource: target,
      enabled: null,
      reason: 'a different extension owns this file'
    };
  }
  const source = await readIfExists(SOURCE);
  if (source !== null && source !== installed) {
    return {
      status: 'stale',
      version: null,
      payloadPath: home,
      detailPath: target,
      registeredSource: target,
      enabled: null,
      reason: 'installed extension differs from the packaged source; rerun cwf host add pi'
    };
  }
  return {
    status: 'installed',
    version: null,
    payloadPath: home,
    detailPath: target,
    registeredSource: target,
    enabled: null,
    reason: null
  };
}
