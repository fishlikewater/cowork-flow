import { cp, mkdir, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function claudeHome() {
  const configured = (process.env.CLAUDE_CONFIG_DIR || '').trim();
  return configured || join(homedir(), '.claude');
}


// Claude Code loads any skills-directory folder that
// carries a plugin manifest as `<name>@skills-dir`, with
// no marketplace and no install record, so one directory
// is the whole install.
function installPath(home) {
  return join(home, 'skills', PLUGIN_NAME);
}


function readManifest(dir, manifestRelative) {
  return readJsonFile(join(dir, ...manifestRelative.split('/')));
}


// `~/.claude/skills/` is a directory users manage by hand,
// so an existing folder counts as ours only when its
// manifest names this plugin; anything else needs an
// explicit --force.
async function ownsInstall(dir, manifestRelative) {
  const manifest = await readManifest(dir, manifestRelative);
  return manifest?.name === PLUGIN_NAME;
}


async function uninstall(target, manifestRelative, { dryRun, force }) {
  if (!(await pathExists(target))) {
    console.log(`cowork-flow Claude Code plugin was not installed; nothing to remove at ${target}`);
    return 0;
  }
  if (!(await ownsInstall(target, manifestRelative))) {
    if (!force) {
      throw new Error(
        `${target} exists but is not the cowork-flow plugin (its ${manifestRelative} `
        + `does not name ${PLUGIN_NAME}). Refusing to delete a folder this installer did not `
        + 'create; use --force to remove it anyway.'
      );
    }
    console.log(`${target} is not the cowork-flow plugin; removing it anyway (--force).`);
  }
  if (dryRun) {
    console.log(`[dry-run] Would remove ${target}`);
    return 0;
  }
  await rm(target, { recursive: true, force: true });
  console.log(`✓ cowork-flow Claude Code plugin uninstalled (removed ${target})`);
  console.log('  Restart Claude Code to drop the plugin from its list.');
  return 0;
}


export async function runInstallClaudeCodePlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = claudeHome();
  const target = installPath(home);
  const { version } = await readPackageInfo();
  // The payload declaration owns the manifest name; read
  // the installed copy through it, not through a second
  // literal.
  const { sourceDir: pluginSrc, manifest } = pluginPayload('claude-code');

  if (remove) {
    return uninstall(target, manifest, { dryRun, force });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Claude Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Claude Code plugin:`);
  console.log(`  Plugin: ${pluginSrc} -> ${target}`);

  // The ownership guard runs before the dry-run exit too:
  // a preview that promises an install the real run
  // refuses is worse than none.
  if (await pathExists(target)) {
    const ours = await ownsInstall(target, manifest);
    if (!ours && !force) {
      throw new Error(
        `${target} already exists and is not the cowork-flow plugin. `
        + 'Use --force to overwrite it, or remove it yourself first.'
      );
    }
    if (ours && !force && !dryRun) {
      const installed = (await readManifest(target, manifest))?.version ?? 'unknown';
      if (installed === version) {
        console.log(`cowork-flow Claude Code plugin already installed at ${target} (${version}).`);
        console.log('Use --force to overwrite.');
        return 0;
      }
      console.log(`Updating cowork-flow Claude Code plugin: ${installed} -> ${version}`);
    }
  }

  if (dryRun) {
    console.log(`  Manifest version: ${version}`);
    console.log('  Loads as cowork-flow@skills-dir in the next Claude Code session; no marketplace or enable step.');
    return 0;
  }

  await mkdir(join(home, 'skills'), { recursive: true });
  await rm(target, { recursive: true, force: true });
  await cp(pluginSrc, target, { recursive: true });
  await stampPayloadManifest(target, manifest, version);

  console.log(`✓ cowork-flow Claude Code plugin installed to ${target}`);
  console.log('  Loads as cowork-flow@skills-dir in the next Claude Code session; no marketplace or enable step.');
  return 0;
}
