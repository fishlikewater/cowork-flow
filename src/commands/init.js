import { resolve } from 'node:path';
import { createInterface } from 'node:readline/promises';

import {
  applyPlan,
  buildInitPlan,
  buildSuperpowersPlan,
  summarizePlan
} from '../lib/copy-template.js';
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

function isAffirmative(answer) {
  const normalized = answer.trim().toLowerCase();
  return normalized === 'y' || normalized === 'yes' || normalized === 'true' || normalized === '1';
}

async function defaultSuperpowersPrompt(io) {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    io.writeOut('Superpowers prompt skipped because stdin is not interactive.\n');
    return true;
  }

  const rl = createInterface({
    input: process.stdin,
    output: process.stdout
  });

  try {
    const answer = await rl.question('Have you already installed Superpowers skills? [y/N] ');
    return isAffirmative(answer);
  } finally {
    rl.close();
  }
}

export async function runInit(args, { io, prompt }) {
  return runInitWithOptions(args, { io, prompt });
}

export async function runInitWithOptions(args, { io, prompt = defaultSuperpowersPrompt }) {
  const options = parseInitArgs(args);
  const packageInfo = await readPackageInfo();
  const plan = await buildInitPlan(options.target, {
    force: options.force,
    version: packageInfo.version
  });

  await applyPlan(plan, { dryRun: options.dryRun });
  io.writeOut(summarizePlan(plan, options.dryRun));

  if (options.dryRun) {
    io.writeOut('Superpowers prompt skipped in dry-run.\n');
    io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
    return 0;
  }

  const alreadyInstalled = await prompt(io);
  if (alreadyInstalled) {
    io.writeOut('Superpowers skills already installed; skipping bundled skills.\n');
    io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
    return 0;
  }

  const superpowersPlan = await buildSuperpowersPlan(options.target, {
    force: options.force
  });
  await applyPlan(superpowersPlan, { dryRun: false });
  io.writeOut(summarizePlan(superpowersPlan, false));
  io.writeOut('Superpowers skills were bundled into .agent/skills.\n');
  io.writeOut('Next: update AGENTS.md and .cowork-flow/config.yaml for this project.\n');
  return 0;
}
