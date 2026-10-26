import { rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { foreignTargetRefusal, installPayloadDir, uninstallPayloadDir } from '../lib/payload-install.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
const LABEL = 'Claude Code plugin';
const LOADS = '  Loads as cowork-flow@skills-dir in the next Claude Code session; no marketplace or enable step.';

// Rendered by `host add`/`host remove`; the installer's own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function claudeHome(env = process.env) {
  const configured = (env.CLAUDE_CONFIG_DIR || '').trim();
  return configured || join(homedir(), '.claude');
}


// Claude Code loads any skills-directory folder carrying a
// plugin manifest as `<name>@skills-dir` — no marketplace and
// no install record — so one directory is the whole install.
function installPath(home) {
  return join(home, 'skills', PLUGIN_NAME);
}

const readManifest = (dir, manifestRelative) => readJsonFile(join(dir, ...manifestRelative.split('/')));


// An existing folder counts as ours only when its manifest
// names this plugin; anything else needs an explicit --force.
async function ownsInstall(dir, manifestRelative) {
  return (await readManifest(dir, manifestRelative))?.name === PLUGIN_NAME;
}


export async function runInstallClaudeCodePlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = claudeHome();
  const target = installPath(home);
  const { version } = await readPackageInfo();
  // The payload declaration owns the manifest name; read the
  // installed copy through it, not through a second literal.
  const { sourceDir: pluginSrc, manifest } = pluginPayload('claude-code');

  if (remove) {
    return uninstallPayloadDir({
      target, label: LABEL, dryRun, force,
      ownsInstall: () => ownsInstall(target, manifest),
      refusal: () => foreignTargetRefusal({ target, probe: manifest, name: PLUGIN_NAME }),
      onPreview: () => console.log(`[dry-run] Would remove ${target}`),
      remove: async () => {
        await rm(target, { recursive: true, force: true });
        console.log(`✓ cowork-flow ${LABEL} uninstalled (removed ${target})`);
        console.log('  Restart Claude Code to drop the plugin from its list.');
      }
    });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Claude Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  return installPayloadDir({
    target, source: pluginSrc, label: LABEL, dryRun, force,
    ownsInstall: () => ownsInstall(target, manifest),
    onForeign: false,
    onExisting: async (ours) => {
      if (!ours || force || dryRun) return false;
      const installed = (await readManifest(target, manifest))?.version ?? 'unknown';
      if (installed !== version) {
        console.log(`Updating cowork-flow ${LABEL}: ${installed} -> ${version}`);
        return false;
      }
      console.log(`cowork-flow ${LABEL} already installed at ${target} (${version}).`);
      console.log('Use --force to overwrite.');
      return true;
    },
    onPreview: () => {
      console.log(`  Manifest version: ${version}`);
      console.log(LOADS);
    },
    onInstalled: () => stampPayloadManifest(target, manifest, version),
    onDone: () => console.log(LOADS)
  });
}


// Read-only installed-state facts for `host inspect`.
export async function inspectInstalledState({ env = process.env } = {}) {
  const target = installPath(claudeHome(env));
  const { manifest } = pluginPayload('claude-code');
  const installed = await readManifest(target, manifest);
  if (!installed) {
    return {
      status: 'missing',
      version: null,
      payloadPath: target,
      detailPath: target,
      registeredSource: target,
      enabled: null,
      reason: 'no plugin manifest'
    };
  }
  if (installed.name !== PLUGIN_NAME) {
    return {
      status: 'missing',
      version: null,
      payloadPath: target,
      detailPath: target,
      registeredSource: target,
      enabled: null,
      reason: 'a different plugin owns this directory'
    };
  }
  const skill = join(target, 'skills', 'cowork-flow-bootstrap', 'SKILL.md');
  if (!(await pathExists(skill))) {
    return {
      status: 'broken',
      version: typeof installed.version === 'string' ? installed.version : null,
      payloadPath: target,
      detailPath: skill,
      registeredSource: target,
      enabled: true,
      reason: 'missing skills/cowork-flow-bootstrap/SKILL.md'
    };
  }
  return {
    status: 'installed',
    version: typeof installed.version === 'string' ? installed.version : null,
    payloadPath: target,
    detailPath: join(target, ...manifest.split('/')),
    registeredSource: target,
    enabled: true,
    reason: null
  };
}
