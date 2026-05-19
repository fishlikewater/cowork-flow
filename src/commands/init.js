import { resolve } from 'node:path';

import { applyPlan, buildInitPlan, summarizePlan } from '../lib/copy-template.js';
import { readPackageInfo } from '../lib/package-info.js';

function parseInitArgs(args) {
  const options = { dryRun: false, force: false, target: process.cwd() };
  for (const arg of args) {
    if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--force') {
      options.force = true;
    } else if (arg.startsWith('--')) {
      throw new Error(`Unknown init option: ${arg}`);
    } else {
      options.target = resolve(arg);
    }
  }
  return options;
}

export async function runInit(args, { io }) {
  const options = parseInitArgs(args);
  const packageInfo = await readPackageInfo();
  const plan = await buildInitPlan(options.target, {
    force: options.force,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun });
  io.writeOut(summarizePlan(plan, options.dryRun));
  io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
  return 0;
}
