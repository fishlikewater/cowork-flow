import { resolve } from 'node:path';

import {
  applyPlan,
  buildReadinessReport,
  buildSyncPlan,
  detectInstalledPlatforms,
  formatReadinessReport,
  summarizePlan
} from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';
import { formatPlatformList } from '../lib/platforms.js';

function parseSyncArgs(args) {
  const options = { dryRun: false, force: false, target: process.cwd() };
  for (const arg of args) {
    if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--force') {
      options.force = true;
    } else if (arg.startsWith('--')) {
      throw new Error(`Unknown sync option: ${arg}`);
    } else {
      options.target = resolve(arg);
    }
  }
  return options;
}

export async function runSync(args, { io, fileSystem }) {
  const options = parseSyncArgs(args);
  const packageInfo = await readPackageInfo();
  const platforms = await detectInstalledPlatforms(options.target);
  const plan = await buildSyncPlan(options.target, {
    force: options.force,
    platforms,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun, fileSystem });
  io.writeOut(summarizePlan(plan, options.dryRun));
  if (options.dryRun) {
    const readiness = await buildReadinessReport(plan, { fileSystem });
    io.writeOut(formatReadinessReport(readiness));
  }
  io.writeOut(`Platforms: ${platforms.length > 0 ? formatPlatformList(platforms) : 'none'}\n`);
  return 0;
}
