import assert from 'node:assert/strict';
import { test } from 'node:test';

import { runUpdate } from '../src/commands/update.js';
import { compareVersions, npmCommandOptions } from '../src/lib/package-info.js';

function createIo() {
  return {
    stdout: '',
    stderr: '',
    writeOut(message) {
      this.stdout += message;
    },
    writeErr(message) {
      this.stderr += message;
    }
  };
}

test('compareVersions compares dotted numeric versions', () => {
  assert.equal(compareVersions('0.3.10', '0.3.11'), -1);
  assert.equal(compareVersions('0.3.10', '0.3.10'), 0);
  assert.equal(compareVersions('0.4.0', '0.3.10'), 1);
});

test('npmCommandOptions enables shell execution on Windows', () => {
  assert.deepEqual(npmCommandOptions('win32'), { shell: true });
});

test('npmCommandOptions keeps direct execution on non-Windows platforms', () => {
  assert.deepEqual(npmCommandOptions('linux'), {});
  assert.deepEqual(npmCommandOptions('darwin'), {});
});

test('update reports current status when already latest', async () => {
  const io = createIo();

  const code = await runUpdate([], {
    io,
    readPackageInfo: async () => ({ version: '0.3.10' }),
    fetchLatestVersion: async () => '0.3.10',
    runGlobalInstall: async () => 0
  });

  assert.equal(code, 0);
  assert.match(io.stdout, /current=0\.3\.10/);
  assert.match(io.stdout, /latest=0\.3\.10/);
  assert.match(io.stdout, /already up to date/);
});

test('update installs latest package when a newer version exists', async () => {
  const io = createIo();
  const installs = [];

  const code = await runUpdate([], {
    io,
    readPackageInfo: async () => ({ version: '0.3.10' }),
    fetchLatestVersion: async () => '0.3.11',
    runGlobalInstall: async (spec) => {
      installs.push(spec);
      return 0;
    }
  });

  assert.equal(code, 0);
  assert.deepEqual(installs, ['cowork-flow@latest']);
  assert.match(io.stdout, /current=0\.3\.10/);
  assert.match(io.stdout, /latest=0\.3\.11/);
  assert.match(io.stdout, /installed cowork-flow@latest/);
});

test('update returns install exit code when global install fails', async () => {
  const io = createIo();

  const code = await runUpdate([], {
    io,
    readPackageInfo: async () => ({ version: '0.3.10' }),
    fetchLatestVersion: async () => '0.3.11',
    runGlobalInstall: async () => 42
  });

  assert.equal(code, 42);
  assert.match(io.stdout, /current=0\.3\.10/);
  assert.match(io.stdout, /latest=0\.3\.11/);
});

test('update degrades to manual command when latest query fails', async () => {
  const io = createIo();

  const code = await runUpdate([], {
    io,
    readPackageInfo: async () => ({ version: '0.3.10' }),
    fetchLatestVersion: async () => {
      throw new Error('registry offline');
    },
    runGlobalInstall: async () => 0
  });

  assert.equal(code, 0);
  assert.match(io.stdout, /current=0\.3\.10/);
  assert.match(io.stdout, /npm install -g cowork-flow@latest/);
  assert.match(io.stderr, /registry offline/);
});

test('update accepts legacy --global --yes flags', async () => {
  const io = createIo();
  const installs = [];

  const code = await runUpdate(['--global', '--yes'], {
    io,
    readPackageInfo: async () => ({ version: '0.3.10' }),
    fetchLatestVersion: async () => '0.3.11',
    runGlobalInstall: async (spec) => {
      installs.push(spec);
      return 0;
    }
  });

  assert.equal(code, 0);
  assert.deepEqual(installs, ['cowork-flow@latest']);
  assert.match(io.stdout, /installed cowork-flow@latest/);
});
