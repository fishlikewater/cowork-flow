import { cp, mkdir, readFile, readdir, rm, rmdir } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { payloadSourceDir } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
// The host scans `plugins/*.{ts,js}` (not recursive), so
// the plugin file is the only thing opencode loads;
// everything else is a sibling directory it never looks
// at.
const PLUGIN_RELATIVE = 'plugins/cowork-flow.js';
const PAYLOAD_RELATIVE = 'cowork-flow';
// A marker inside the plugin file: opencode has no
// manifest and no install record, so the file's own
// content is the only way to tell our plugin from a
// same-named file a user put there.
const PLUGIN_MARKER = 'CoworkFlowPlugin';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


// opencode reads its global config from
// $XDG_CONFIG_HOME/opencode, falling back to
// ~/.config/opencode — on every platform.
function opencodeHome() {
  const configured = (process.env.XDG_CONFIG_HOME || '').trim();
  return configured ? join(configured, 'opencode') : join(homedir(), '.config', 'opencode');
}


function pluginPath(home) {
  return join(home, ...PLUGIN_RELATIVE.split('/'));
}


function payloadPath(home) {
  return join(home, PAYLOAD_RELATIVE);
}


async function ownsInstall(home) {
  try {
    const source = await readFile(pluginPath(home), 'utf8');
    return source.includes(PLUGIN_MARKER);
  } catch {
    return false;
  }
}


// `~/.config/opencode/plugins/` is a directory users drop
// their own plugins into. Removing our file and payload
// leaves it empty when we were its only occupant, and an
// empty plugins/ is a shell we created, so it goes too; a
// directory still holding someone else's stays.
async function removeIfEmpty(dir) {
  try {
    if ((await readdir(dir)).length === 0) {
      await rmdir(dir);
      return true;
    }
  } catch {
    // Missing or non-empty: nothing to clean up either
    // way.
  }
  return false;
}


async function uninstall(home, { dryRun, force }) {
  const plugin = pluginPath(home);
  const payload = payloadPath(home);
  const present = (await pathExists(plugin)) || (await pathExists(payload));
  if (!present) {
    console.log(`cowork-flow OpenCode plugin was not installed; nothing to remove at ${home}`);
    return 0;
  }
  if (!(await ownsInstall(home)) && !force) {
    throw new Error(
      `${plugin} exists but does not look like the cowork-flow plugin (no ${PLUGIN_MARKER} `
      + 'in it). Refusing to delete files this installer did not create; use --force to '
      + 'remove them anyway.'
    );
  }
  if (!(await ownsInstall(home))) {
    console.log(`${plugin} is not the cowork-flow plugin; removing it anyway (--force).`);
  }
  if (dryRun) {
    console.log(`[dry-run] Would remove ${plugin} and ${payload}`);
    return 0;
  }
  await rm(plugin, { force: true });
  await rm(payload, { recursive: true, force: true });
  const cleaned = await removeIfEmpty(join(home, 'plugins'));
  console.log(`✓ cowork-flow OpenCode plugin uninstalled (removed ${plugin} and ${payload})`);
  if (cleaned) {
    console.log(`  Removed the now-empty ${join(home, 'plugins')}`);
  }
  console.log('  Restart OpenCode to drop the plugin from its list.');
  return 0;
}


export async function runInstallOpenCodePlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = opencodeHome();
  // The declaration names the payload directory.
  // opencode's plugin format has no manifest, so this
  // installer resolves only the directory and stamps
  // nothing.
  const pluginSrc = payloadSourceDir('opencode');

  if (remove) {
    return uninstall(home, { dryRun, force });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`OpenCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow OpenCode plugin:`);
  console.log(`  Plugin: ${pluginSrc} -> ${home}`);

  // The ownership guard runs before the dry-run exit too:
  // a preview that promises an install the real run
  // refuses is worse than none.
  if (await pathExists(pluginPath(home))) {
    const ours = await ownsInstall(home);
    if (!ours && !force) {
      throw new Error(
        `${pluginPath(home)} already exists and is not the cowork-flow plugin. `
        + 'Use --force to overwrite it, or remove it yourself first.'
      );
    }
    if (!ours) {
      console.log(`${pluginPath(home)} is not the cowork-flow plugin; overwriting it anyway (--force).`);
    }
  }

  if (dryRun) {
    console.log(`  Registers ${join(payloadPath(home), 'skills')} through the plugin's config hook; no CLI step.`);
    return 0;
  }

  await mkdir(join(home, 'plugins'), { recursive: true });
  await rm(pluginPath(home), { force: true });
  await rm(payloadPath(home), { recursive: true, force: true });
  await cp(join(pluginSrc, 'plugins', 'cowork-flow.js'), pluginPath(home));
  await cp(join(pluginSrc, PAYLOAD_RELATIVE), payloadPath(home), { recursive: true });

  console.log(`✓ cowork-flow OpenCode plugin installed to ${home}`);
  console.log('  Loads in the next OpenCode session; no marketplace, registry or enable step.');
  return 0;
}
