// cowork-flow DSH workflow-state hook.
//
// DSH-native equivalent of the Codex/Claude hooks
// (template/.codex/hooks/inject-workflow-state.py and its Claude sibling):
// this preset plugin registers ONE system-prompt section, rendered last
// (order 1000, after identity/persona/tool guidance), whose text is the
// `<workflow-state>` block produced by the SAME Python protocol the other
// hosts use (adapters/host/workflow_state_hook.py), so the injected content
// is structurally identical across hosts.
//
// The block is refreshed per user message (`agent/session-start` warms it,
// `agent/inbox/claimed` refreshes it) and after lifecycle commands settle
// (`tools/result`), then cached per agent; each prompt assembly re-renders
// the current cached value in place — replace semantics, no accumulation
// across turns or steps. Between refreshes the text is byte-stable, so the
// static prompt prefix stays cacheable and the dynamic cost is confined to
// the trailing block.
//
// Degradation is silent: no `.cowork-flow` root, a missing Python, a broken
// runtime, or the `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`
// switches all yield an empty section, and the workspace AGENTS.md gate
// falls back to running the navigator manually.

import { execFile } from 'node:child_process';
import { stat } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';

export const name = 'workflow-state-hook';
export const inject = ['systemPrompt'];

const SECTION_NAME = 'cowork-flow-workflow-state';
const SECTION_ORDER = 1000;
const REFRESH_TIMEOUT_MS = 15000;
const EXEC_OPTIONS = {
  timeout: REFRESH_TIMEOUT_MS,
  windowsHide: true,
  maxBuffer: 1024 * 1024,
};
const NO_ROOT_MARKER = '__COWORK_FLOW_NO_ROOT__';
// How long a "no .cowork-flow root" verdict is trusted for one cwd. Bounded
// on purpose: a project that installs cowork-flow mid-session becomes visible
// after at most one TTL, at the cost of at most one interpreter probe.
const NO_ROOT_TTL_MS = 30_000;
const noRootCache = new Map();

// Python 3.9+ protocol reused from the host hook adapters. It resolves the
// `.cowork-flow` root from the given cwd, loads the shared
// workflow_state_hook module, and prints the full hook context block.
const PYTHON_PROTOCOL = `\
import sys
from pathlib import Path

cwd = sys.argv[1]
current = Path(cwd).resolve()
root = None
while True:
    if (current / ".cowork-flow").is_dir():
        root = current
        break
    if current == current.parent:
        break
    current = current.parent
if root is None:
    print(${JSON.stringify(NO_ROOT_MARKER)})
    raise SystemExit(0)
scripts_dir = root / ".cowork-flow" / "scripts"
sys.path.insert(0, str(scripts_dir))
from adapters.host.workflow_state_hook import build_hook_context
print(build_hook_context(
    root,
    {"cwd": cwd},
    host="dsh",
    adapter="dsh.preset.systemPrompt",
    preamble=(
        "<dsh-runtime>\\n"
        "injection: agent-preset workflow-state section, refreshed per user message\\n"
        "runtime_context_identity: formal subagent sessions bind before workflow-state injection\\n"
        "</dsh-runtime>",
    ),
))
`;

// The first interpreter that ran the protocol successfully; a missing one is
// dropped so a later refresh can rediscover (e.g. after a PATH change).
let workingPython = null;

// Cowork-flow lifecycle commands executed through any tool. Matching the
// command text (not the tool name) keeps the trigger stable across tool
// surface changes.
const LIFECYCLE_COMMAND = /\.cowork-flow[\\/]run(?:\.cmd)?(?:\s+[^\s"']*)?\s+(task|subagent|resume)\b/;


/**
 * True when a tool argument value embeds a cowork-flow lifecycle command.
 * Accepts strings and JSON-serializable structures; never throws.
 */
export function isLifecycleCommand(value) {
  try {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    return typeof text === 'string' && LIFECYCLE_COMMAND.test(text);
  } catch {
    return false;
  }
}


function hooksDisabled() {
  return (
    process.env.COWORK_FLOW_HOOKS === '0'
    || process.env.COWORK_FLOW_DISABLE_HOOKS === '1'
  );
}


function discoverCandidates() {
  const candidates = [];
  for (const variable of ['COWORK_FLOW_PYTHON', 'PYTHON']) {
    const value = process.env[variable];
    if (value && value.trim()) {
      candidates.push({ command: value.trim(), args: [] });
    }
  }
  candidates.push({ command: 'python3', args: [] });
  candidates.push({ command: 'python', args: [] });
  candidates.push({ command: 'py', args: ['-3'] });
  return candidates;
}


function tryPython(candidate, cwd) {
  return new Promise((resolve) => {
    execFile(
      candidate.command,
      [...candidate.args, '-c', PYTHON_PROTOCOL, cwd],
      EXEC_OPTIONS,
      (error, stdout) => {
        if (error) {
          // ENOENT = the interpreter does not exist (try the next one).
          // Any other failure means the interpreter ran but the protocol
          // failed — the candidate works, the project runtime does not.
          resolve({ missing: error.code === 'ENOENT', output: '' });
          return;
        }
        resolve({ missing: false, output: stdout.trim() });
      },
    );
  });
}


function normalize(output) {
  if (!output || output === NO_ROOT_MARKER) {
    return '';
  }
  return output;
}


/**
 * Test seam: forget the memoized interpreter so the next call rediscovers.
 */
export function resetWorkingPython() {
  workingPython = null;
}


/**
 * Nearest ancestor of `cwd` whose `.cowork-flow` entry is a directory, or
 * `null` when no such ancestor exists. Mirrors the root resolution inside
 * the Python protocol so a project without cowork-flow never pays for an
 * interpreter spawn at all.
 */
export async function findCoworkRoot(cwd) {
  let current = resolve(cwd);
  for (;;) {
    try {
      const entry = await stat(join(current, '.cowork-flow'));
      if (entry.isDirectory()) {
        return current;
      }
    } catch {
      // Missing or inaccessible — keep walking up.
    }
    const parent = dirname(current);
    if (parent === current) {
      return null;
    }
    current = parent;
  }
}


/**
 * Produce the `<workflow-state>` hook context block for a workspace cwd.
 * Empty string means "contribute nothing" (no root, hooks disabled, no
 * usable interpreter, or a broken runtime).
 */
export async function runWorkflowState(cwd) {
  if (hooksDisabled() || !cwd) {
    return '';
  }
  const resolved = resolve(cwd);
  const cached = noRootCache.get(resolved);
  if (cached !== undefined && cached > Date.now()) {
    return '';
  }
  if ((await findCoworkRoot(resolved)) === null) {
    if (noRootCache.size > 1000) {
      noRootCache.clear();
    }
    noRootCache.set(resolved, Date.now() + NO_ROOT_TTL_MS);
    return '';
  }
  if (workingPython !== null) {
    const result = await tryPython(workingPython, cwd);
    if (!result.missing) {
      return normalize(result.output);
    }
    workingPython = null;
  }
  for (const candidate of discoverCandidates()) {
    const result = await tryPython(candidate, cwd);
    if (result.missing) {
      continue;
    }
    workingPython = candidate;
    return normalize(result.output);
  }
  return '';
}


export function apply(ctx) {
  // One cache entry per agent: { text, inflight, queued }. The WeakMap key
  // is the live Agent object the events and the assembly context both carry.
  const states = new WeakMap();

  const refresh = (agent) => {
    const cwd = agent && agent.cwd;
    if (!cwd) {
      return;
    }
    let entry = states.get(agent);
    if (!entry) {
      entry = { text: '', inflight: false, queued: false };
      states.set(agent, entry);
    }
    if (entry.inflight) {
      // A refresh arrived while one was running (e.g. several lifecycle
      // commands back to back). Re-run once after it settles so the latest
      // on-disk state wins instead of being dropped.
      entry.queued = true;
      return;
    }
    entry.inflight = true;
    runWorkflowState(cwd)
      .then((text) => {
        entry.text = text;
      })
      .catch(() => {
        entry.text = '';
      })
      .finally(() => {
        entry.inflight = false;
        if (entry.queued) {
          entry.queued = false;
          refresh(agent);
        }
      });
  };

  ctx.on('agent/session-start', (payload) => refresh(payload && payload.agent));
  ctx.on('agent/inbox/claimed', (payload) => refresh(payload && payload.agent));
  // Intra-turn refresh: a lifecycle command just settled, so the next prompt
  // assembly should already see the new state instead of the stale block.
  ctx.on('tools/result', (exec) => {
    const agent = exec && exec.agent;
    if (!agent || !isLifecycleCommand(exec && exec.arguments)) {
      return;
    }
    refresh(agent);
  });

  ctx.effect(() => ctx.systemPrompt.section({
    name: SECTION_NAME,
    order: SECTION_ORDER,
    text: (assembleContext) => {
      const agent = assembleContext && assembleContext.agent;
      const entry = agent ? states.get(agent) : undefined;
      return entry ? entry.text : '';
    },
  }), 'workflow-state.section()');
}
