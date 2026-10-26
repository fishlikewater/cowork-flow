import { cp, readFile, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

import { parseInstallArgs, pathExists } from '../lib/install-support.js';
import { installPayloadDir, pruneEmptyDir, uninstallPayloadDir } from '../lib/payload-install.js';
import { templateRoot } from '../lib/paths.js';
import { payloadSourceDir } from '../lib/plugin-payload.js';

const LABEL = 'OpenCode plugin';
// The host scans `plugins/*.{ts,js}` (not recursive): the plugin file
// is all it loads, and its own marker is the only ownership signal.
const PLUGIN_RELATIVE = 'plugins/cowork-flow.js';
const PAYLOAD_RELATIVE = 'cowork-flow';
const PLUGIN_MARKER = 'CoworkFlowPlugin';

// Rendered by `host add`/`host remove`; the installer's own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


// $XDG_CONFIG_HOME/opencode, falling back to ~/.config/opencode — on every platform.
function opencodeHome(env = process.env) {
  const configured = (env.XDG_CONFIG_HOME || '').trim();
  return configured ? join(configured, 'opencode') : join(homedir(), '.config', 'opencode');
}

const pluginPath = (home) => join(home, ...PLUGIN_RELATIVE.split('/'));
const payloadPath = (home) => join(home, PAYLOAD_RELATIVE);


async function ownsInstall(home) {
  try {
    return (await readFile(pluginPath(home), 'utf8')).includes(PLUGIN_MARKER);
  } catch {
    return false;
  }
}


export async function runInstallOpenCodePlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = opencodeHome();
  const plugin = pluginPath(home);
  const payload = payloadPath(home);
  // The declaration names the payload directory; there is no manifest to stamp.
  const pluginSrc = payloadSourceDir('opencode');

  if (remove) {
    return uninstallPayloadDir({
      target: plugin, label: LABEL, displayTarget: home, dryRun, force,
      exists: async () => (await pathExists(plugin)) || (await pathExists(payload)),
      ownsInstall: () => ownsInstall(home),
      refusal: () => new Error(
        `${plugin} exists but does not look like the cowork-flow plugin (no ${PLUGIN_MARKER} in it). `
        + 'Refusing to delete files this installer did not create; use --force to remove them anyway.'
      ),
      onPreview: () => console.log(`[dry-run] Would remove ${plugin} and ${payload}`),
      remove: async () => {
        await rm(plugin, { force: true });
        await rm(payload, { recursive: true, force: true });
        const cleaned = await pruneEmptyDir(join(home, 'plugins'));
        console.log(`✓ cowork-flow ${LABEL} uninstalled (removed ${plugin} and ${payload})`);
        if (cleaned) console.log(`  Removed the now-empty ${join(home, 'plugins')}`);
        console.log('  Restart OpenCode to drop the plugin from its list.');
      }
    });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`OpenCode plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  return installPayloadDir({
    target: plugin, source: join(pluginSrc, 'plugins', 'cowork-flow.js'),
    label: LABEL, displaySource: pluginSrc, displayTarget: home, dryRun, force,
    ownsInstall: () => ownsInstall(home),
    onPreview: () => console.log(`  Registers ${join(payload, 'skills')} through the plugin's config hook; no CLI step.`),
    onInstalled: async () => {
      await rm(payload, { recursive: true, force: true });
      await cp(join(pluginSrc, PAYLOAD_RELATIVE), payload, { recursive: true });
      // Refresh the cached runtime copy the transport shim falls back
      // to outside any cowork-flow project; a project's copy wins.
      const mainScriptsSrc = join(templateRoot, '.cowork-flow', 'scripts');
      if (await pathExists(mainScriptsSrc)) {
        await cp(mainScriptsSrc, join(payload, 'runtime', 'scripts'), { recursive: true, force: true });
      }
    },
    onDone: () => console.log('  Loads in the next OpenCode session; no marketplace, registry or enable step.')
  });
}


// Read-only installed-state facts for `host inspect`. OpenCode has no version
// manifest, so version stays null; the doctor compares file contents.
export async function inspectInstalledState({ env = process.env } = {}) {
  const home = opencodeHome(env);
  const plugin = pluginPath(home);
  const payload = payloadPath(home);
  let installed;
  try {
    installed = await readFile(plugin, 'utf8');
  } catch {
    return {
      status: 'missing',
      version: null,
      payloadPath: payload,
      registeredSource: plugin,
      enabled: null,
      reason: 'no plugin file'
    };
  }
  if (!installed.includes(PLUGIN_MARKER)) {
    return {
      status: 'missing',
      version: null,
      payloadPath: payload,
      registeredSource: plugin,
      enabled: null,
      reason: 'a different plugin owns this file'
    };
  }
  for (const relative of ['plugin-core.js', 'skills/cowork-flow-bootstrap/SKILL.md']) {
    if (!(await pathExists(join(payload, ...relative.split('/'))))) {
      return {
        status: 'broken',
        version: null,
        payloadPath: payload,
        registeredSource: plugin,
        enabled: true,
        reason: `missing cowork-flow/${relative}`
      };
    }
  }
  return {
    status: 'installed',
    version: null,
    payloadPath: payload,
    registeredSource: plugin,
    enabled: true,
    reason: null
  };
}
