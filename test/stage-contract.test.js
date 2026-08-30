import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';
import { stageContractBlock as opencodeStageContract } from '../template/.opencode/plugins/cowork-flow.js';

const NODE = process.execPath;
const SCRIPTS = join(packageRoot, 'template', '.cowork-flow', 'scripts');
const SERVER = join(SCRIPTS, 'adapters', 'mcp', 'state_server.py');
const MATRIX_FILE = join(packageRoot, 'test', 'fixtures', 'stage-contract-matrix.json');
const matrix = JSON.parse(readFileSync(MATRIX_FILE, 'utf8'));

// One matrix case drives every host line: python build_hook_context, the zcode
// hook over stdin, and the opencode stageContractBlock called directly. Every
// line must produce a byte-identical <stage-contract> block, and the case's
// assert fields must hold on the python output (the semantic source).
function writeMatrixFixture(root, caseDef) {
  const workflow = join(root, '.cowork-flow');
  const taskPath = caseDef.taskPath || '.cowork-flow/tasks/08-30-demo';
  mkdirSync(join(workflow, 'tasks'), { recursive: true });
  mkdirSync(join(workflow, '.runtime', 'sessions'), { recursive: true });
  mkdirSync(join(workflow, 'spec', 'contracts'), { recursive: true });
  mkdirSync(join(workflow, 'spec', 'runtime'), { recursive: true });
  const taskDir = join(workflow, taskPath.replace(/^\.cowork-flow\//, ''));
  mkdirSync(taskDir, { recursive: true });
  const underlying = caseDef.underlying || caseDef.status;
  writeFileSync(
    join(taskDir, 'task.json'),
    JSON.stringify({ status: underlying, title: 'Demo' })
  );
  writeFileSync(
    join(taskDir, 'implement.jsonl'),
    (caseDef.entries || []).map((entry) => JSON.stringify(entry)).join('\n') + '\n'
  );
  if (caseDef.anchor) {
    const lines = ['# Decision Anchor', '', '## 目标', '', caseDef.anchor.goal || 'Goal.', ''];
    if (caseDef.anchor.acceptance && caseDef.anchor.acceptance.length > 0) {
      lines.push('## 验收标准', '');
      for (const item of caseDef.anchor.acceptance) lines.push(`- [ ] ${item}`);
      lines.push('');
    }
    if (caseDef.anchor.validationCommands && caseDef.anchor.validationCommands.length > 0) {
      lines.push('## 验证命令', '');
      for (const cmd of caseDef.anchor.validationCommands) lines.push(`- ${cmd}`);
      lines.push('');
    }
    if (caseDef.anchor.scopeBoundary) {
      lines.push('## 范围边界', '', caseDef.anchor.scopeBoundary);
    }
    writeFileSync(join(taskDir, 'decision-anchor.md'), lines.join('\n'));
  }
  writeFileSync(
    join(workflow, 'spec', 'contracts', 'workflow-state-templates.md'),
    [
      '[workflow-state:in_progress]',
      '活动任务正在执行。',
      '[/workflow-state:in_progress]',
    ].join('\n')
  );
  writeFileSync(
    join(workflow, 'spec', 'runtime', 'contract-registry.json'),
    JSON.stringify({ schemaVersion: 1, contracts: [] }) + '\n'
  );
  writeFileSync(
    join(workflow, '.runtime', 'sessions', 'probe.json'),
    JSON.stringify({ active_task_path: '' }) // placeholder, replaced per line
  );
  if (caseDef.status === 'delegated_subtask') {
    // Delegated lines bind a runtime context (subagent record) instead of a
    // main session, so python/zcode resolve status="delegated_subtask" and
    // render the read-only variant — matching the opencode direct call.
    const subagentsDir = join(workflow, '.runtime', 'subagents');
    mkdirSync(subagentsDir, { recursive: true });
    writeFileSync(
      join(subagentsDir, 'rtx_probe.json'),
      JSON.stringify({
        schema_version: 2,
        runtime_context_id: 'rtx_probe',
        scope: 'subagent',
        host: 'codex',
        adapter: 'codex.hook',
        agent_type: 'cowork-implement',
        role: 'implement',
        task_dir: taskPath,
        status: 'bound',
        assignment: { goal: caseDef.anchor?.goal || 'Child slice.' },
        bound_context_key: null,
      })
    );
  }
  return { taskPath, taskDir };
}

function extractStageContract(context) {
  const match = context.match(/<stage-contract task="[^"]*">[\s\S]*?<\/stage-contract>/);
  assert.ok(match, 'stage-contract block must be present');
  return match[0];
}

function runPythonBlock(root, caseDef) {
  const taskPath = caseDef.taskPath || '.cowork-flow/tasks/08-30-demo';
  const delegated = caseDef.status === 'delegated_subtask';
  const hookInput = delegated
    ? '{"COWORK_FLOW_RUNTIME_CONTEXT_ID": "rtx_probe"}'
    : '{"COWORK_FLOW_CONTEXT_ID": "probe"}';
  const script = `
import sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(SCRIPTS)})
from adapters.host.workflow_state_hook import build_hook_context
context = build_hook_context(
    Path(${JSON.stringify(root)}),
    ${hookInput},
    host="codex",
    adapter="codex.hook",
    preamble=(),
    session_start=False,
)
print(context)
`;
  const python = spawnSync('python3', ['-c', script], { encoding: 'utf8' });
  assert.equal(python.status, 0, `python probe failed: ${python.stderr}`);
  return extractStageContract(python.stdout);
}

function runZcodeBlock(root, caseDef) {
  const hook = join(packageRoot, 'template', '.zcode', 'hooks', 'inject-context.js');
  const delegated = caseDef.status === 'delegated_subtask';
  const input = {
    hook_event_name: 'UserPromptSubmit',
    ...(delegated ? {} : { session_id: 'probe' }),
  };
  const env = delegated ? { ...process.env, COWORK_FLOW_RUNTIME_CONTEXT_ID: 'rtx_probe' } : undefined;
  const zcode = spawnSync(
    NODE,
    [hook],
    {
      encoding: 'utf8',
      cwd: root,
      env,
      input: JSON.stringify(input),
    }
  );
  assert.equal(zcode.status, 0, `zcode hook failed: ${zcode.stderr}`);
  const context = JSON.parse(zcode.stdout).hookSpecificOutput.additionalContext;
  return extractStageContract(context);
}

function runOpencodeBlock(root, caseDef) {
  const taskPath = caseDef.taskPath || '.cowork-flow/tasks/08-30-demo';
  const block = opencodeStageContract(
    root,
    taskPath,
    caseDef.status,
    caseDef.status === 'delegated_subtask'
  );
  assert.ok(block, 'opencode stage-contract must be present');
  return block;
}

function assertCase(block, assertDef) {
  if (assertDef.closed) {
    assert.ok(block.endsWith('</stage-contract>'), 'block must be closed');
  }
  if (assertDef.maxLen) {
    assert.ok(block.length <= assertDef.maxLen, `budget: ${block.length} chars`);
  }
  if (assertDef.scopeMin) {
    const scope = block.match(/^Scope: (.+)$/m);
    assert.ok(scope, 'Scope row must exist');
    const entries = scope[1].split('; ').filter((part) => !part.startsWith('('));
    assert.ok(entries.length >= assertDef.scopeMin, `Scope must keep >= ${assertDef.scopeMin} entries`);
  }
  if (assertDef.scopeExact) {
    assert.match(block, new RegExp(`^${escapeRegex(assertDef.scopeExact)}$`, 'm'));
  }
  if (assertDef.scopeContains) {
    assert.match(block, new RegExp(escapeRegex(assertDef.scopeContains)));
  }
  if (assertDef.specsExact) {
    assert.match(block, new RegExp(`^${escapeRegex(assertDef.specsExact)}$`, 'm'));
  }
  if (assertDef.verifyContains) {
    assert.match(block, new RegExp(escapeRegex(assertDef.verifyContains)));
  }
  if (assertDef.gates) {
    assert.match(block, /Gates: edits outside Scope are review blockers/);
  }
  if (assertDef.gatesReadonly) {
    assert.match(block, new RegExp(escapeRegex(assertDef.gatesReadonly)));
  }
  if (assertDef.noAgentMutable) {
    assert.doesNotMatch(block, /\[agent-mutable\]/);
  }
  if (assertDef.noVerify) {
    assert.doesNotMatch(block, /^Verify:/m);
  }
  if (assertDef.noSpecs) {
    assert.doesNotMatch(block, /^Specs:/m);
  }
}

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

for (const caseDef of matrix.cases) {
  test(`matrix case ${caseDef.name}: byte-identical across python/zcode/opencode + assertions`, () => {
    const pythonRoot = mkdtempSync(join(tmpdir(), 'cowork-flow-mx-py-'));
    const zcodeRoot = mkdtempSync(join(tmpdir(), 'cowork-flow-mx-js-'));
    const opencodeRoot = mkdtempSync(join(tmpdir(), 'cowork-flow-mx-oc-'));
    try {
      const taskPath = caseDef.taskPath || '.cowork-flow/tasks/08-30-demo';
      for (const root of [pythonRoot, zcodeRoot, opencodeRoot]) {
        writeMatrixFixture(root, caseDef);
        // The python host resolves the bare key "probe"; the zcode host
        // prefixes it — both need a bound session file.
        writeFileSync(
          join(root, '.cowork-flow', '.runtime', 'sessions', 'probe.json'),
          JSON.stringify({ active_task_path: taskPath })
        );
        writeFileSync(
          join(root, '.cowork-flow', '.runtime', 'sessions', 'zcode_probe.json'),
          JSON.stringify({ active_task_path: taskPath })
        );
      }

      const pythonBlock = runPythonBlock(pythonRoot, caseDef);
      const zcodeBlock = runZcodeBlock(zcodeRoot, caseDef);
      const opencodeBlock = runOpencodeBlock(opencodeRoot, caseDef);

      assert.equal(zcodeBlock, pythonBlock, `${caseDef.name}: zcode must equal python`);
      assert.equal(opencodeBlock, pythonBlock, `${caseDef.name}: opencode must equal python`);
      assertCase(pythonBlock, caseDef.assert);
    } finally {
      rmSync(pythonRoot, { recursive: true, force: true });
      rmSync(zcodeRoot, { recursive: true, force: true });
      rmSync(opencodeRoot, { recursive: true, force: true });
    }
  });
}