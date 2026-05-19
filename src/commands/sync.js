import { resolve } from 'node:path';

import { applyPlan, buildSyncPlan, summarizePlan } from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';

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

export async function runSync(args, { io }) {
  const options = parseSyncArgs(args);
  const packageInfo = await readPackageInfo();
  const plan = await buildSyncPlan(options.target, {
    force: options.force,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun });
  io.writeOut(summarizePlan(plan, options.dryRun));
  return 0;
}
