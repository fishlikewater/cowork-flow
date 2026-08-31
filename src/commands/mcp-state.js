import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const DIR_WORKFLOW = '.cowork-flow';

function defaultIo() {
  return {
    writeOut(message) {
      process.stdout.write(message);
    },
    writeErr(message) {
      process.stderr.write(message);
    },
  };
}

function findNearestWorkflowRoot(startDir) {
  let current = resolve(startDir);
  // Same semantics as the MCP server's root resolution (get_repo_root):
  // walk up to the nearest directory containing .cowork-flow/, so a client
  // launching the globally registered server inside any project subdirectory
  // still lands on the right facts.
  for (;;) {
    if (existsSync(join(current, DIR_WORKFLOW))) {
      return current;
    }
    const parent = resolve(current, '..');
    if (parent === current) {
      return null;
    }
    current = parent;
  }
}

export async function runMcpState(args, options = {}) {
  const io = options.io ?? defaultIo();  const root = findNearestWorkflowRoot(process.cwd());
  if (root === null) {
    io.writeErr(
      'Error: no .cowork-flow/ found from the current directory; '
        + 'run this inside a cowork-flow project.\n'
    );
    return 1;
  }

  const runnerName = process.platform === 'win32' ? 'run.cmd' : 'run';
  const runner = join(root, DIR_WORKFLOW, runnerName);
  if (!existsSync(runner)) {
    io.writeErr(`Error: workflow runner not found: ${runner}\n`);
    return 1;
  }

  return await new Promise((resolveExit) => {
    const child = spawn(runner, ['mcp-state', ...args], {
      stdio: 'inherit',
      cwd: root,
      // Windows: newer Node (v24+) throws EINVAL when spawning .cmd files
      // directly; routing through cmd.exe matches how npm shims launch.
      shell: process.platform === 'win32',
    });
    child.on('error', (error) => {
      io.writeErr(`Error: failed to launch ${runner}: ${error.message}\n`);
      resolveExit(1);
    });
    child.on('exit', (code) => {
      resolveExit(code ?? 1);
    });
  });
}
