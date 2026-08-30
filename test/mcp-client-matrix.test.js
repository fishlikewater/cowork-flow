import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';
import { skipWithoutShell } from './shell-capability.js';

const SERVER = join(
  packageRoot,
  'template',
  '.cowork-flow',
  'scripts',
  'adapters',
  'mcp',
  'state_server.py'
);
const PYTHONPATH = join(packageRoot, 'template', '.cowork-flow', 'scripts');

// Client-equivalent launch matrix: every MCP client starts the server as a
// stdio command from some cwd. Two shapes cover it:
//   1. project runner -> <project>/.cowork-flow/run mcp-state
//   2. global CLI      -> cowork-flow mcp-state  (PATH-resolved, walk-up root)
// Both must answer initialize + tools/list identically.

async function runSession(command, args, cwd, env = process.env) {
  const requests = [
    JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: { protocolVersion: '2025-06-18' },
    }),
    JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }),
  ].join('\n');
  const { stdout } = await new Promise((resolveRun) => {
    const child = execFile(
      command,
      args,
      { cwd, encoding: 'utf8', env, timeout: 20000 },
      (error, stdoutOut) => {
        resolveRun({ error, stdout: stdoutOut ?? '' });
      }
    );
    child.stdin?.end(requests);
  });
  return stdout
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

async function createProject(t, { stubToServer }) {
  const tempDir = await mkdtemp(join(tmpdir(), 'cowork-flow-mcp-matrix-'));
  t.after(async () => {
    await rm(tempDir, { recursive: true, force: true });
  });
  const project = join(tempDir, 'project');
  const workflow = join(project, '.cowork-flow');
  await mkdir(join(workflow, 'tasks', '08-29-matrix'), { recursive: true });
  await writeFile(
    join(workflow, 'tasks', '08-29-matrix', 'task.json'),
    JSON.stringify({ status: 'in_progress', title: 'Matrix' }),
    'utf8'
  );
  const body = stubToServer
    ? [
        '#!/bin/sh',
        `PYTHONPATH="${PYTHONPATH}" exec python3 "${SERVER}" "$@"`,
        '',
      ].join('\n')
    : '#!/bin/sh\nexit 0\n';
  await writeFile(join(workflow, 'run'), body, {
    encoding: 'utf8',
    mode: 0o755,
  });
  const nested = join(project, 'nested', 'deep');
  await mkdir(nested, { recursive: true });
  return { project, nested };
}

test('matrix: project-level runner serves the full session', async (t) => {
  if (skipWithoutShell(t)) return;
  const { project } = await createProject(t, { stubToServer: true });
  const env = { ...process.env, PYTHONPATH };

  const replies = await runSession(
    join(project, '.cowork-flow', 'run'),
    ['mcp-state'],
    project,
    env
  );

  assert.equal(replies.length, 2, 'notification-free: one reply per request');
  assert.equal(replies[0].result.serverInfo.name, 'cowork-flow-facts');
  assert.deepEqual(
    replies[1].result.tools.map((tool) => tool.name),
    ['task_state', 'task_list', 'task_specs', 'task_scope']
  );
});

test('matrix: global CLI walks up from a nested directory to the project runner', async (t) => {
  const globalCli = await new Promise((resolveWhich) => {
    execFile('which', ['cowork-flow'], (error, stdout) => {
      resolveWhich(error ? null : stdout.trim());
    });
  });
  if (!globalCli) {
    return; // no global installation on this host; CI covers the runner shape
  }
  const { nested } = await createProject(t, { stubToServer: true });

  const replies = await runSession(globalCli, ['mcp-state'], nested);

  assert.equal(replies.length, 2);
  assert.equal(replies[0].result.serverInfo.name, 'cowork-flow-facts');
  assert.deepEqual(
    replies[1].result.tools.map((tool) => tool.name),
    ['task_state', 'task_list', 'task_specs', 'task_scope']
  );
});
