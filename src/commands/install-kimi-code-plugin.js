import { cp, mkdir, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
const MANIFEST_MARKER = 'cowork-flow';

// Rendered by `host add`/`host remove`; the installer's
// own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function kimiHome() {
  const configured = (process.env.KIMI_CODE_HOME || '').trim();
  // The host rejects a relative plugin root, and that path
  // is printed for the user to paste, so a relative
  // KIMI_CODE_HOME must not survive here.
  return configured ? resolve(configured) : join(homedir(), '.kimi-code');
}


// The host's registry records the path a plugin was
// installed from and re-reads it on every reinstall, so
// this source directory has to survive upgrades. It is
// deliberately NOT `plugins/managed/`: that is the host's
// own copy, and a directory there without a registry
// record is exactly the half-installed state the doctor
// reports.
function sourceDir(home) {
  return join(home, 'plugins', 'sources', PLUGIN_NAME);
}


// Read the installed copy through the payload
// declaration's own manifest path instead of keeping a
// second literal in sync.
async function ownsInstall(target, manifestRelative) {
  const manifest = await readJsonFile(join(target, ...manifestRelative.split('/')));
  return manifest?.name === MANIFEST_MARKER;
}


// Kimi Code has no CLI subcommand for plugins:
// installation is TUI-only. The installer materializes the
// source and hands over the one slash command that does
// the rest (the host copies the payload, validates the
// manifest and writes its registry record).
function printInstallInstruction(target) {
  console.log('  Install it in Kimi Code (one time):');
  console.log(`    /plugins install ${target}`);
  console.log('  Then run /reload. Verify with /plugins list.');
}


async function uninstall(home, manifestRelative, { dryRun, force }) {
  const target = sourceDir(home);
  if (!(await pathExists(target))) {
    console.log(`cowork-flow Kimi Code plugin source was not installed; nothing to remove at ${target}`);
    return 0;
  }
  if (!(await ownsInstall(target, manifestRelative)) && !force) {
    throw new Error(
      `${target} exists but is not the cowork-flow plugin (its ${manifestRelative} `
      + `does not name ${MANIFEST_MARKER}). Refusing to delete a directory this installer did `
      + 'not create; use --force to remove it anyway.'
    );
  }
  if (!(await ownsInstall(target, manifestRelative))) {
    console.log(`${target} is not the cowork-flow plugin; removing it anyway (--force).`);
  }
  if (dryRun) {
    console.log(`[dry-run] Would remove ${target}`);
    console.log('  The installed copy stays in Kimi Code; remove it there with /plugins remove cowork-flow.');
    return 0;
  }
  await rm(target, { recursive: true, force: true });
  console.log(`✓ cowork-flow Kimi Code plugin source removed (${target})`);
  // The host's remove only drops the registry record; its
  // managed copy and this source directory stay on disk,
  // so say so.
  console.log('  Still registered in Kimi Code? Run /plugins remove cowork-flow, then delete');
  console.log(`  ${join(home, 'plugins', 'managed', PLUGIN_NAME)} if it remains.`);
  return 0;
}


export async function runInstallKimiPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = kimiHome();
  const target = sourceDir(home);
  const { sourceDir: pluginSrc, manifest } = pluginPayload('kimi-code');
  const { version } = await readPackageInfo();

  if (remove) {
    return uninstall(home, manifest, { dryRun, force });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Kimi Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Kimi Code plugin source:`);
  console.log(`  Source: ${pluginSrc} -> ${target}`);

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
    if (!ours) {
      console.log(`${target} is not the cowork-flow plugin; overwriting it anyway (--force).`);
    }
  }

  if (dryRun) {
    printInstallInstruction(target);
    return 0;
  }

  await mkdir(join(home, 'plugins', 'sources'), { recursive: true });
  await rm(target, { recursive: true, force: true });
  await cp(pluginSrc, target, { recursive: true });
  // The host reads the version from this manifest when it
  // installs the plugin, so the source must carry the
  // package version: the shipped copy tracks the release,
  // a materialized one must not depend on it.
  await stampPayloadManifest(target, manifest, version);

  console.log(`✓ cowork-flow Kimi Code plugin source installed to ${target}`);
  printInstallInstruction(target);
  return 0;
}
