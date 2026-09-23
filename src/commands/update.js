import {
  compareVersions,
  fetchLatestVersion,
  readPackageInfo,
  runGlobalInstall
} from '../lib/package-info.js';
import { parseFlags } from '../lib/cli-flags.js';

function parseUpdateArgs(args) {
  const { flags } = parseFlags(args, { boolean: ['--dry-run'] });
  return { dryRun: Boolean(flags['--dry-run']) };
}

function buildUpdateReadinessReport({ current, latest, installCommand, wouldInstall, warnings = [] }) {
  return {
    wouldCopy: [],
    wouldSkipProtected: [],
    wouldRemoveObsolete: [],
    hostAssetRefresh: [],
    pendingRecovery: [],
    warnings,
    update: {
      current,
      latest,
      wouldInstall,
      installCommand
    }
  };
}

function formatReadinessReport(report) {
  return `readiness=${JSON.stringify(report)}\n`;
}

export async function runUpdate(args, deps = {}) {
  const io = deps.io;
  const readInfo = deps.readPackageInfo ?? readPackageInfo;
  const fetchLatest = deps.fetchLatestVersion ?? fetchLatestVersion;
  const installGlobal = deps.runGlobalInstall ?? runGlobalInstall;
  const options = parseUpdateArgs(args);
  const packageInfo = await readInfo();
  const current = packageInfo.version;
  const installCommand = 'npm install -g cowork-flow@latest';

  let latest = null;
  try {
    latest = await fetchLatest('cowork-flow');
  } catch (error) {
    const warning = error instanceof Error ? error.message : String(error);
    io.writeErr(`${warning}\n`);
    io.writeOut(`current=${current}\n`);
    if (options.dryRun) {
      io.writeOut(formatReadinessReport(buildUpdateReadinessReport({
        current,
        latest,
        installCommand,
        wouldInstall: false,
        warnings: [warning]
      })));
    }
    io.writeOut(`Unable to query npm latest. Run: ${installCommand}\n`);
    return 0;
  }

  io.writeOut(`current=${current}\n`);
  io.writeOut(`latest=${latest}\n`);

  const wouldInstall = compareVersions(current, latest) < 0;
  if (options.dryRun) {
    io.writeOut(formatReadinessReport(buildUpdateReadinessReport({
      current,
      latest,
      installCommand,
      wouldInstall
    })));
    if (!wouldInstall) {
      io.writeOut('cowork-flow is already up to date.\n');
    } else {
      io.writeOut(`dry-run would-run: ${installCommand}\n`);
    }
    return 0;
  }

  if (!wouldInstall) {
    io.writeOut('cowork-flow is already up to date.\n');
    return 0;
  }

  const code = await installGlobal('cowork-flow@latest');
  if (code === 0) {
    io.writeOut('installed cowork-flow@latest\n');
  }
  return code;
}
