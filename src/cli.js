import { stdin as input, stdout as output } from 'node:process';
import { createInterface } from 'node:readline/promises';

import { runInit } from './commands/init.js';
import { runSync } from './commands/sync.js';
import { runUpdate } from './commands/update.js';
import { readPackageInfo } from './lib/package-info.js';

const HELP = `cowork-flow

Usage:
  cowork-flow init [target] [--developer <name>] [--dry-run] [--force]
  cowork-flow update
  cowork-flow sync [target] [--dry-run] [--force]
  cowork-flow --version
  cowork-flow --help
`;

function defaultIo() {
  return {
    writeOut(message) {
      process.stdout.write(message);
    },
    writeErr(message) {
      process.stderr.write(message);
    }
  };
}

async function defaultPrompt(message) {
  if (!input.isTTY || !output.isTTY) {
    return null;
  }
  const readline = createInterface({ input, output });
  try {
    return await readline.question(message);
  } finally {
    readline.close();
  }
}

export async function main(argv = process.argv.slice(2), options = {}) {
  const io = options.io ?? defaultIo();
  const prompt = Object.hasOwn(options, 'prompt') ? options.prompt : defaultPrompt;
  const [command, ...args] = argv;

  try {
    if (!command || command === '--help' || command === '-h') {
      io.writeOut(HELP);
      return 0;
    }

    if (command === '--version' || command === '-v') {
      const packageInfo = await readPackageInfo();
      io.writeOut(`${packageInfo.version}\n`);
      return 0;
    }

    if (command === 'init') {
      return await runInit(args, { io, prompt });
    }

    if (command === 'sync') {
      return await runSync(args, { io });
    }

    if (command === 'update') {
      return await runUpdate(args, { io });
    }

    io.writeErr(`Unknown command: ${command}\n`);
    return 1;
  } catch (error) {
    io.writeErr(`${error instanceof Error ? error.message : String(error)}\n`);
    return 1;
  }
}
