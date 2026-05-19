import {
  compareVersions,
  fetchLatestVersion,
  readPackageInfo,
  runGlobalInstall
} from '../lib/package-info.js';

function parseUpdateArgs(args) {
  const options = { global: false, yes: false };
  for (const arg of args) {
    if (arg === '--global') {
      options.global = true;
    } else if (arg === '--yes') {
      options.yes = true;
    } else {
      throw new Error(`Unknown update option: ${arg}`);
    }
  }
  return options;
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
    io.writeErr(`${error instanceof Error ? error.message : String(error)}\n`);
    io.writeOut(`current=${current}\n`);
    io.writeOut(`Unable to query npm latest. Run: ${installCommand}\n`);
    return 0;
  }

  io.writeOut(`current=${current}\n`);
  io.writeOut(`latest=${latest}\n`);

  if (compareVersions(current, latest) >= 0) {
    io.writeOut('cowork-flow is already up to date.\n');
    return 0;
  }

  if (options.global && options.yes) {
    const code = await installGlobal('cowork-flow@latest');
    if (code === 0) {
      io.writeOut('installed cowork-flow@latest\n');
    }
    return code;
  }

  io.writeOut(`Run: ${installCommand}\n`);
  return 0;
}
