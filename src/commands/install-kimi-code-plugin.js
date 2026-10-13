import { rm } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

import { parseInstallArgs, pathExists, readJsonFile } from '../lib/install-support.js';
import { foreignTargetRefusal, installPayloadDir, uninstallPayloadDir } from '../lib/payload-install.js';
import { readPackageInfo } from '../lib/package-info.js';
import { pluginPayload, stampPayloadManifest } from '../lib/plugin-payload.js';

const PLUGIN_NAME = 'cowork-flow';
const MANIFEST_MARKER = 'cowork-flow';
const LABEL = 'Kimi Code plugin source';

// Rendered by `host add`/`host remove`; the installer's own vocabulary.
export const FLAGS = ['--dry-run', '--force', '--uninstall'];


function kimiHome() {
  const configured = (process.env.KIMI_CODE_HOME || '').trim();
  // The host rejects a relative plugin root; the resolved path is printed to paste.
  return configured ? resolve(configured) : join(homedir(), '.kimi-code');
}

// The host re-reads this source directory on every reinstall,
// so it must survive upgrades; deliberately NOT
// `plugins/managed/` (the host's own copy, doctor's half-installed case).
function sourceDir(home) {
  return join(home, 'plugins', 'sources', PLUGIN_NAME);
}


// The installed copy is read through the payload declaration's own manifest path.
async function ownsInstall(target, manifestRelative) {
  const manifest = await readJsonFile(join(target, ...manifestRelative.split('/')));
  return manifest?.name === MANIFEST_MARKER;
}


// Kimi Code has no CLI subcommand for plugins: installation
// is TUI-only. This installer materializes the source and
// hands over the one slash command that does the rest (the
// host copies, validates and registers the payload).
function printInstallInstruction(target) {
  console.log('  Install it in Kimi Code (one time):');
  console.log(`    /plugins install ${target}`);
  console.log('  Then run /reload. Verify with /plugins list.');
}


export async function runInstallKimiPlugin(args = []) {
  const { dryRun, force, uninstall: remove } = parseInstallArgs(args);
  const home = kimiHome();
  const target = sourceDir(home);
  const { sourceDir: pluginSrc, manifest } = pluginPayload('kimi-code');
  const { version } = await readPackageInfo();

  if (remove) {
    return uninstallPayloadDir({
      target, label: LABEL, dryRun, force,
      ownsInstall: () => ownsInstall(target, manifest),
      refusal: () => foreignTargetRefusal({
        target, probe: manifest, name: MANIFEST_MARKER, noun: 'directory'
      }),
      onPreview: () => {
        console.log(`[dry-run] Would remove ${target}`);
        console.log('  The installed copy stays in Kimi Code; remove it there with /plugins remove cowork-flow.');
      },
      remove: async () => {
        await rm(target, { recursive: true, force: true });
        console.log(`✓ cowork-flow ${LABEL} removed (${target})`);
        // The host's remove only drops the registry record; its
        // managed copy and this source directory stay on disk.
        console.log('  Still registered in Kimi Code? Run /plugins remove cowork-flow, then delete');
        console.log(`  ${join(home, 'plugins', 'managed', PLUGIN_NAME)} if it remains.`);
      }
    });
  }

  if (!(await pathExists(pluginSrc))) {
    throw new Error(`Kimi Code plugin source missing at ${pluginSrc}. Reinstall cowork-flow.`);
  }

  return installPayloadDir({
    target, source: pluginSrc, label: LABEL, sourceKind: 'Source', dryRun, force,
    ownsInstall: () => ownsInstall(target, manifest),
    onPreview: () => printInstallInstruction(target),
    onInstalled: () => stampPayloadManifest(target, manifest, version),
    onDone: () => printInstallInstruction(target)
  });
}
