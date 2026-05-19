import { readPackageInfo } from './lib/package-info.js';

const HELP = `cowork-flow

Usage:
  cowork-flow init [target] [--dry-run] [--force]
  cowork-flow update [--global] [--yes]
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

export async function main(argv = process.argv.slice(2), options = {}) {
  const io = options.io ?? defaultIo();
  const [command] = argv;

  if (!command || command === '--help' || command === '-h') {
    io.writeOut(HELP);
    return 0;
  }

  if (command === '--version' || command === '-v') {
    const packageInfo = await readPackageInfo();
    io.writeOut(`${packageInfo.version}\n`);
    return 0;
  }

  io.writeErr(`Unknown command: ${command}\n`);
  return 1;
}
