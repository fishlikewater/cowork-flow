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
// `agent/inbox/claimed` refreshes it) and cached per agent; each prompt
// assembly re-renders the current cached value in place — replace semantics,
// no accumulation across turns or steps. Between refreshes the text is
// byte-stable, so the static prompt prefix stays cacheable and the dynamic
// cost is confined to the trailing block.
//
// Degradation is silent: no `.cowork-flow` root, a missing Python, a broken
// runtime, or the `COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`
// switches all yield an empty section, and the workspace AGENTS.md gate
// falls back to running the navigator manually.

import { execFile } from 'node:child_process';

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
 * Produce the `<workflow-state>` hook context block for a workspace cwd.
 * Empty string means "contribute nothing" (no root, hooks disabled, no
 * usable interpreter, or a broken runtime).
 */
export async function runWorkflowState(cwd) {
  if (hooksDisabled()) {
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
  // One cache entry per agent: { text, inflight }. The WeakMap key is the
  // live Agent object the events and the assembly context both carry.
  const states = new WeakMap();

  const refresh = (agent) => {
    const cwd = agent && agent.cwd;
    if (!cwd) {
      return;
    }
    let entry = states.get(agent);
    if (!entry) {
      entry = { text: '', inflight: false };
      states.set(agent, entry);
    }
    if (entry.inflight) {
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
      });
  };

  ctx.on('agent/session-start', (payload) => refresh(payload && payload.agent));
  ctx.on('agent/inbox/claimed', (payload) => refresh(payload && payload.agent));

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
