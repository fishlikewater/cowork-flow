import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';

import { packageRoot } from '../src/lib/paths.js';
import { shellRunner, skipWithoutShell } from './shell-capability.js';

const execFileAsync = promisify(execFile);
const cliEntry = join(packageRoot, 'bin', 'cowork-flow.js');

async function createProjectWithFakeRunner(t, runnerBody) {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-mcp-passthrough-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  const project = join(tempDir, 'project');
  const workflowDir = join(project, '.cowork-flow');
  await mkdir(workflowDir, { recursive: true });
  await writeFile(
    join(workflowDir, 'run'),
    ['#!/bin/sh', runnerBody, 'exit 0'].join('\n'),
    { encoding: 'utf8', mode: 0o755 }
  );
  // A nested subdirectory proves the walk-up resolution.
  const nested = join(project, 'nested', 'deep');
  await mkdir(nested, { recursive: true });
  return { project, nested };
}

test('mcp-state passthrough executes the nearest project runner and relays stdio', async (t) => {
  if (skipWithoutShell(t)) return;
  const { nested } = await createProjectWithFakeRunner(
    t,
    'printf \'{"jsonrpc":"2.0","id":1,"method":"probe"}\\n\'\n'
    + 'printf \'args: %s\\n\' "$*" >&2\n'
  );

  const result = await new Promise((resolveRun) => {
    const child = execFile(
      process.execPath,
      [cliEntry, 'mcp-state'],
      { cwd: nested, encoding: 'utf8' },
      (error, stdout, stderr) => {
        resolveRun({ error, stdout, stderr, code: error ? error.code : 0 });
      }
    );
    child.stdin?.end('client-hello\n');
  });

  assert.equal(result.code, 0);
  assert.match(result.stdout, /"method":"probe"/);
  // Arguments arrive at the runner exactly as the client sent them.
  assert.match(result.stderr, /args: mcp-state/);
});

test('mcp-state passthrough relays the runner exit code', async (t) => {
  if (skipWithoutShell(t)) return;
  const { project } = await createProjectWithFakeRunner(t, 'exit 5');

  const outcome = await new Promise((resolveRun) => {
    execFile(
      process.execPath,
      [cliEntry, 'mcp-state'],
      { cwd: project, encoding: 'utf8' },
      (error, _stdout, _stderr) => {
        resolveRun({ code: error ? error.code : 0 });
      }
    );
  });

  assert.equal(outcome.code, 5);
});

test('mcp-state passthrough fails clearly outside a cowork-flow project', async (t) => {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-mcp-noroot-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });

  await assert.rejects(
    execFileAsync(process.execPath, [cliEntry, 'mcp-state'], {
      cwd: tempDir,
      encoding: 'utf8',
    }),
    /no \.cowork-flow\/ found/
  );
});

test('mcp-state is wired into the CLI dispatch', async () => {
  const { ALIASES, COMMANDS } = await import('../src/commands/registry.js');

  assert.ok(
    COMMANDS.some((entry) => entry.path.join(' ') === 'mcp serve'),
    'the registry declares no `mcp serve` command'
  );
  const alias = ALIASES.find((entry) => entry.name === 'mcp-state');
  assert.ok(alias, 'the registry declares no mcp-state alias');
  // Permanent: this spelling is already written into users' MCP client configs.
  assert.equal(alias.permanent, true);
  assert.deepEqual(alias.command, ['mcp', 'serve']);
});

// The new spelling has to reach the project runner with the runner's own
// subcommand key, which is unrelated to the npm CLI's naming.
test('mcp serve passes the runner key through under the new spelling', async (t) => {
  if (skipWithoutShell(t)) return;
  const { project } = await createProjectWithFakeRunner(
    t,
    'printf \'{"jsonrpc":"2.0","id":1,"method":"probe"}\\n\'\n'
    + 'printf \'args: %s\\n\' "$*" >&2\n'
  );

  const result = await new Promise((resolveRun) => {
    execFile(
      process.execPath,
      [cliEntry, 'mcp', 'serve'],
      { cwd: project, encoding: 'utf8' },
      (error, stdout, stderr) => {
        resolveRun({ error, stdout, stderr, code: error ? error.code : 0 });
      }
    );
  });

  assert.equal(result.code, 0);
  assert.match(result.stdout, /"method":"probe"/);
  assert.match(result.stderr, /args: mcp-state/);
});
