import { access, cp, mkdir, readFile, rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

import { parseFlags } from '../lib/cli-flags.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
const MANIFEST_MARKER = 'cowork-flow';

// Declared so `host add`/`host remove` can render the flags this installer
// accepts without keeping a second copy of the list.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function parseArgs(args) {
  const { flags } = parseFlags(args, { boolean: FLAGS });
  return {
    dryRun: Boolean(flags['--dry-run']),
    force: Boolean(flags['--force']),
    uninstall: Boolean(flags['--uninstall'])
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


function kimiHome() {
  const configured = (process.env.KIMI_CODE_HOME || '').trim();
  return configured || join(homedir(), '.kimi-code');
}


// A stable source directory of our own. Kimi Code's registry records the path a
// plugin was installed from and re-reads it on every reinstall, so this location
// has to survive upgrades — the same constraint the codex marketplace source
// carries. It is deliberately NOT the host's `plugins/managed/` tree: that is the
// host's copy, and a directory there without a registry record is exactly the
// half-installed state the doctor reports.
function sourceDir(home) {
  return join(home, 'plugins', 'sources', PLUGIN_NAME);
}


async function ownsInstall(target) {
  try {
    const manifest = JSON.parse(
      await readFile(join(target, '.kimi-plugin', 'plugin.json'), 'utf8')
    );
    return manifest?.name === MANIFEST_MARKER;
  } catch {
    return false;
  }
}


// Kimi Code has no CLI subcommand for plugins — installation is TUI-only. So the
// installer stops at materializing the source and hands the user the one slash
// command that does the rest: the host copies the payload into
// `plugins/managed/`, validates the manifest and writes its own registry record.
// Reimplementing those three steps here would mean keeping a second copy of
// host-private logic (see docs/hosts.md for the verified record shape).
function printInstallInstruction(target) {
  console.log('  Install it in Kimi Code (one time):');
  console.log(`    /plugins install ${target}`);
  console.log('  Then run /reload. Verify with /plugins list.');
}


async function uninstall(home, { dryRun, force }) {
  const target = sourceDir(home);
  if (!(await pathExists(target))) {
    console.log(`cowork-flow Kimi Code plugin source was not installed; nothing to remove at ${target}`);
    return 0;
  }
  if (!(await ownsInstall(target)) && !force) {
    throw new Error(
      `${target} exists but is not the cowork-flow plugin (its .kimi-plugin/plugin.json `
      + `does not name ${MANIFEST_MARKER}). Refusing to delete a directory this installer did `
      + 'not create; use --force to remove it anyway.'
    );
  }
  if (!(await ownsInstall(target))) {
    console.log(`${target} is not the cowork-flow plugin; removing it anyway (--force).`);
  }
  if (dryRun) {
    console.log(`[dry-run] Would remove ${target}`);
    console.log('  The installed copy stays in Kimi Code; remove it there with /plugins remove cowork-flow.');
    return 0;
  }
  await rm(target, { recursive: true, force: true });
  console.log(`✓ cowork-flow Kimi Code plugin source removed (${target})`);
  // The host's remove only drops the registry record; its managed copy and the
  // source directory stay on disk. Say so instead of implying a clean sweep.
  console.log('  Still registered in Kimi Code? Run /plugins remove cowork-flow, then delete');
  console.log(`  ${join(home, 'plugins', 'managed', PLUGIN_NAME)} if it remains.`);
  return 0;
}


export async function runInstallKimiPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseArgs(args);
  const home = kimiHome();
  const target = sourceDir(home);
  const { sourceDir: pluginSrc, manifest } = pluginPayload('kimi-code');
  const { version } = await readPackageInfo();

  if (remove) {
    return uninstall(home, { dryRun, force });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Kimi Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  console.log(`${dryRun ? '[dry-run] Would install' : 'Installing'} cowork-flow Kimi Code plugin source:`);
  console.log(`  Source: ${pluginSrc} -> ${target}`);

  // The ownership guard runs before the dry-run exit too: a preview that says
  // "would install" over a directory the real run then refuses would be worse
  // than no preview at all.
  if (await pathExists(target)) {
    const ours = await ownsInstall(target);
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
  // The host reads the version from this manifest when it installs the plugin, so
  // the source has to carry the package version — the shipped one tracks the
  // release, but a materialized copy must not depend on that.
  await stampPayloadManifest(target, manifest, version);

  console.log(`✓ cowork-flow Kimi Code plugin source installed to ${target}`);
  printInstallInstruction(target);
  return 0;
}
