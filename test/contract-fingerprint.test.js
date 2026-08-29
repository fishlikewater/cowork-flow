import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';

const NODE = process.execPath;

// The registry below deliberately lists contract object keys in a different
// order than the JSON document order, and the two contracts out of id order,
// so a non-stable serialization would produce a different fingerprint per
// implementation. All three implementations must sort keys before hashing.
const REGISTRY = {
  schemaVersion: 1,
  contracts: [
    {
      readWhen: ['before formal subagent dispatch'],
      id: 'RUNTIME_CONTEXT_DISPATCH_V2',
      digest: [
        'Formal subagent work is keyed by cowork_runtime_context_id.',
        'Explicit shim bind records bound_context_key before formal output is accepted.',
      ],
      path: '.cowork-flow/spec/contracts/subagent-dispatch.md',
    },
    {
      readWhen: ['before implementation'],
      path: '.cowork-flow/spec/contracts/plan-binding.md',
      id: 'PLAN_BINDING_LITE_V1',
      digest: ['A non-Tiny task must bind a plan file before start.'],
    },
  ],
};

const CONTRACT_FILES = {
  '.cowork-flow/spec/contracts/subagent-dispatch.md':
    '# Runtime-context subagent dispatch\n\nFormal dispatch is keyed by runtime context.\n',
  '.cowork-flow/spec/contracts/plan-binding.md':
    '# Plan binding\n\nA non-Tiny task binds a plan file before start.\n',
};

async function createFixture() {
  const root = await mkdtemp(join(tmpdir(), 'cowork-flow-fingerprint-'));
  await mkdir(join(root, '.cowork-flow', 'spec', 'runtime'), { recursive: true });
  await writeFile(
    join(root, '.cowork-flow', 'spec', 'runtime', 'contract-registry.json'),
    `${JSON.stringify(REGISTRY, null, 2)}\n`,
    'utf8'
  );
  for (const [rel, content] of Object.entries(CONTRACT_FILES)) {
    const dest = join(root, rel);
    await mkdir(join(dest, '..'), { recursive: true });
    await writeFile(dest, content, 'utf8');
  }
  return root;
}

function fingerprintFromPython(root) {
  const script = `
import sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(join(packageRoot, 'template', '.cowork-flow', 'scripts'))})
from adapters.host.workflow_state_hook import contract_fingerprint, _load_contract_registry
contracts, _ = _load_contract_registry(Path(${JSON.stringify(root)}))
print(contract_fingerprint(Path(${JSON.stringify(root)}), contracts))
`;
  const result = spawnSync('python3', ['-c', script], { encoding: 'utf8' });
  assert.equal(
    result.status,
    0,
    `python fingerprint probe failed: ${result.stderr || result.stdout}`
  );
  return result.stdout.trim();
}

function fingerprintFromZcodeHook(root) {
  const hook = join(
    packageRoot,
    'template',
    '.zcode',
    'hooks',
    'inject-context.js'
  );
  const result = spawnSync(
    NODE,
    [hook],
    {
      encoding: 'utf8',
      cwd: root,
      input: JSON.stringify({ hook_event_name: 'SessionStart', cwd: root }),
    }
  );
  assert.equal(
    result.status,
    0,
    `zcode hook failed: ${result.stderr || result.stdout}`
  );
  const parsed = JSON.parse(result.stdout);
  const match = parsed.hookSpecificOutput.additionalContext.match(
    /<contract-digest fingerprint="([a-f0-9]{16})">/
  );
  assert.ok(match, 'zcode hook should emit the full digest block with fingerprint');
  return match[1];
}

async function fingerprintFromOpencode(root) {
  const pluginPath = join(
    packageRoot,
    'template',
    '.opencode',
    'plugins',
    'cowork-flow.js'
  );
  const { contractFingerprint } = await import(pathToFileURL(pluginPath).href);
  return contractFingerprint(root, REGISTRY.contracts);
}

test('contract fingerprint is identical across zcode, python and opencode', async (t) => {
  const root = await createFixture();
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });

  const pythonFp = fingerprintFromPython(root);
  const zcodeFp = fingerprintFromZcodeHook(root);
  const opencodeFp = await fingerprintFromOpencode(root);

  assert.match(pythonFp, /^[a-f0-9]{16}$/);
  assert.equal(zcodeFp, pythonFp, 'zcode JS hook must hash identically to the Python core');
  assert.equal(opencodeFp, pythonFp, 'opencode plugin must hash identically to the Python core');
});

test('fingerprint changes identically on all three when a contract file changes', async (t) => {
  const root = await createFixture();
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });

  const beforePython = fingerprintFromPython(root);
  const beforeZcode = fingerprintFromZcodeHook(root);
  const beforeOpencode = await fingerprintFromOpencode(root);
  assert.equal(beforeZcode, beforePython);
  assert.equal(beforeOpencode, beforePython);

  const specPath = join(root, '.cowork-flow', 'spec', 'contracts', 'plan-binding.md');
  await writeFile(specPath, CONTRACT_FILES['.cowork-flow/spec/contracts/plan-binding.md'] + '<!-- drift -->\n', 'utf8');

  const afterPython = fingerprintFromPython(root);
  const afterZcode = fingerprintFromZcodeHook(root);
  const afterOpencode = await fingerprintFromOpencode(root);
  assert.notEqual(afterPython, beforePython, 'changed contract content must move the fingerprint');
  assert.equal(afterZcode, afterPython);
  assert.equal(afterOpencode, afterPython);
});