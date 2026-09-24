import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { readPackageInfo } from '../src/lib/package-info.js';
import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

async function runCli(args) {
  return execFileAsync(process.execPath, [join(packageRoot, 'bin', 'cowork-flow.js'), ...args], {
    cwd: packageRoot,
    encoding: 'utf8'
  });
}

test('package smoke loads the CLI and answers a real command', async () => {
  const { version } = await readPackageInfo();
  const versionResult = await runCli(['--version']);
  assert.equal(versionResult.stdout.trim(), version);

  const hostResult = await runCli(['host', 'list', '--json', packageRoot]);
  const report = JSON.parse(hostResult.stdout);
  assert.ok(report.hosts.length > 0);
  assert.ok(report.hosts.some((host) => host.id === 'codex'));
  assert.equal(hostResult.stderr, '');
});
