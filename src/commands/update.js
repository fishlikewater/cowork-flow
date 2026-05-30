import {
  compareVersions,
  fetchLatestVersion,
  readPackageInfo,
  runGlobalInstall
} from '../lib/package-info.js';

function validateUpdateArgs(args) {
  for (const arg of args) {
    if (arg !== '--global' && arg !== '--yes') {
      throw new Error(`Unknown update option: ${arg}`);
    }
  }
}

export async function runUpdate(args, deps = {}) {
  const io = deps.io;
  const readInfo = deps.readPackageInfo ?? readPackageInfo;
  const fetchLatest = deps.fetchLatestVersion ?? fetchLatestVersion;
  const installGlobal = deps.runGlobalInstall ?? runGlobalInstall;
  validateUpdateArgs(args);
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

  const code = await installGlobal('cowork-flow@latest');
  if (code === 0) {
    io.writeOut('installed cowork-flow@latest\n');
  }
  return code;
}
