import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';

const NODE = process.execPath;
const SCRIPTS = join(packageRoot, 'template', '.cowork-flow', 'scripts');
const SERVER = join(SCRIPTS, 'adapters', 'mcp', 'state_server.py');

// Shared fixture: one in_progress task whose artifacts cover every field the
// stage-contract renders (scope entries incl. a directory decoy, spec
// pointers, verification commands, scope boundary).
function writeStageContractFixture(root) {
  const workflow = join(root, '.cowork-flow');
  mkdirSync(join(workflow, 'tasks', '08-30-demo'), { recursive: true });
  mkdirSync(join(workflow, '.runtime', 'sessions'), { recursive: true });
  mkdirSync(join(workflow, 'spec', 'contracts'), { recursive: true });
  mkdirSync(join(workflow, 'spec', 'runtime'), { recursive: true });
  writeFileSync(
    join(workflow, 'tasks', '08-30-demo', 'task.json'),
    JSON.stringify({ status: 'in_progress', title: 'Demo' })
  );
  writeFileSync(
    join(workflow, 'tasks', '08-30-demo', 'implement.jsonl'),
    [
      JSON.stringify({ file: 'src/demo.py', reason: 'main' }),
      JSON.stringify({ file: 'src/next.py', reason: 'planned', type: 'planned-file' }),
      JSON.stringify({ file: 'src/', reason: 'dir ctx', type: 'directory' }),
      JSON.stringify({ file: '.cowork-flow/spec/backend/index.md', reason: 'backend guide' }),
      JSON.stringify({ file: '.cowork-flow/spec/guides/index.md', reason: 'guides' }),
    ].join('\n') + '\n'
  );
  writeFileSync(
    join(workflow, 'tasks', '08-30-demo', 'decision-anchor.md'),
    [
      '# Decision Anchor',
      '',
      '## 目标',
      'Serve the stage contract identically on every host.',
      '',
      '## 验收标准',
      '- [ ] AC-001: byte-identical stage-contract',
      '',
      '## 验证命令',
      '- npm run test:fast',
      '- python3 -m pytest tests/ -q',
      '',
      '## 范围边界',
      '范围内: src/ only',
    ].join('\n')
  );
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
    join(workflow, '.runtime', 'sessions', 'zcode_probe.json'),
    JSON.stringify({ active_task_path: '.cowork-flow/tasks/08-30-demo' })
  );
  // The python host resolves the bare key "probe" (COWORK_FLOW_CONTEXT_ID),
  // the zcode host prefixes it — both must find a bound session.
  writeFileSync(
    join(workflow, '.runtime', 'sessions', 'probe.json'),
    JSON.stringify({ active_task_path: '.cowork-flow/tasks/08-30-demo' })
  );
}

function extractStageContract(context) {
  const match = context.match(/<stage-contract task="[^"]*">[\s\S]*?<\/stage-contract>/);
  assert.ok(match, 'stage-contract block must be present');
  return match[0];
}

test('stage-contract block is byte-identical between python and zcode hosts', () => {
  const pythonRoot = mkdtempSync(join(tmpdir(), 'cowork-flow-sc-py-'));
  const zcodeRoot = mkdtempSync(join(tmpdir(), 'cowork-flow-sc-js-'));
  try {
    writeStageContractFixture(pythonRoot);
    writeStageContractFixture(zcodeRoot);

    const pythonScript = `
import sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(SCRIPTS)})
from adapters.host.workflow_state_hook import build_hook_context
context = build_hook_context(
    Path(${JSON.stringify(pythonRoot)}),
    {"COWORK_FLOW_CONTEXT_ID": "probe"},
    host="codex",
    adapter="codex.hook",
    preamble=(),
    session_start=False,
)
print(context)
`;
    const python = spawnSync('python3', ['-c', pythonScript], { encoding: 'utf8' });
    assert.equal(python.status, 0, `python probe failed: ${python.stderr}`);
    const pythonBlock = extractStageContract(python.stdout);

    const hook = join(packageRoot, 'template', '.zcode', 'hooks', 'inject-context.js');
    const zcode = spawnSync(
      NODE,
      [hook],
      {
        encoding: 'utf8',
        cwd: zcodeRoot,
        input: JSON.stringify({
          hook_event_name: 'UserPromptSubmit',
          session_id: 'probe',
        }),
      }
    );
    assert.equal(zcode.status, 0, `zcode hook failed: ${zcode.stderr}`);
    const zcodeContext = JSON.parse(zcode.stdout).hookSpecificOutput.additionalContext;
    const zcodeBlock = extractStageContract(zcodeContext);

    assert.equal(zcodeBlock, pythonBlock);
    assert.ok(pythonBlock.length <= 1200, `stage-contract budget: ${pythonBlock.length} chars`);
    // Directory entries authorize nothing: the scope line lists exactly the
    // file-scope entries, in whitelist order (spec pointers are themselves
    // whitelisted files, matching lifecycle_checks semantics).
    assert.match(
      pythonBlock,
      /Scope: src\/demo\.py; src\/next\.py; \.cowork-flow\/spec\/backend\/index\.md; \.cowork-flow\/spec\/guides\/index\.md \[agent-mutable\]/
    );
    assert.match(pythonBlock, /Specs: \.cowork-flow\/spec\/backend\/index\.md; \.cowork-flow\/spec\/guides\/index\.md/);
    assert.match(pythonBlock, /Verify: npm run test:fast; python3 -m pytest tests\/ -q/);
    assert.match(pythonBlock, /Gates: edits outside Scope are review blockers/);
  } finally {
    rmSync(pythonRoot, { recursive: true, force: true });
    rmSync(zcodeRoot, { recursive: true, force: true });
  }
});
