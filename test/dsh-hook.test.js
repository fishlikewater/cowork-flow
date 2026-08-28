import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { findCoworkRoot, isLifecycleCommand, runWorkflowState, resetWorkingPython } from '../presets/dsh/plugins/workflow-state.js';
import { packageRoot } from '../src/lib/paths.js';


test('produces the workflow-state block for a cowork-flow root', async () => {
  const text = await runWorkflowState(packageRoot);

  assert.match(text, /<workflow-state[^>]*>/);
  assert.match(text, /Status: /);
  assert.match(text, /<cowork-runtime host="dsh"/);
  assert.match(text, /adapter="dsh\.preset\.systemPrompt"/);
});


test('returns empty text outside a cowork-flow root', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-hook-noroot-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  assert.equal(await runWorkflowState(dir), '');
});


test('honours the hook disable switches', async (t) => {
  const previousHooks = process.env.COWORK_FLOW_HOOKS;
  const previousDisable = process.env.COWORK_FLOW_DISABLE_HOOKS;
  t.after(() => {
    restore('COWORK_FLOW_HOOKS', previousHooks);
    restore('COWORK_FLOW_DISABLE_HOOKS', previousDisable);
  });

  process.env.COWORK_FLOW_HOOKS = '0';
  assert.equal(await runWorkflowState(packageRoot), '');

  delete process.env.COWORK_FLOW_HOOKS;
  process.env.COWORK_FLOW_DISABLE_HOOKS = '1';
  assert.equal(await runWorkflowState(packageRoot), '');

  function restore(name, value) {
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
});


test('degrades to empty text when the protocol fails', async (t) => {
  const previousPython = process.env.COWORK_FLOW_PYTHON;
  t.after(() => {
    restore('COWORK_FLOW_PYTHON', previousPython);
    resetWorkingPython();
  });

  // node exists wherever these tests run, but `node -c <python source>` exits
  // non-zero — an interpreter that runs yet fails the protocol. The hook must
  // treat that as "contribute nothing", not as a missing interpreter.
  resetWorkingPython();
  process.env.COWORK_FLOW_PYTHON = process.execPath;
  assert.equal(await runWorkflowState(packageRoot), '');

  function restore(name, value) {
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
});


test('skips the interpreter entirely outside a cowork-flow root', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-hook-noroot-'));
  const marker = join(dir, 'ran-marker');
  const stub = join(dir, 'python-stub.sh');
  const previousPython = process.env.COWORK_FLOW_PYTHON;
  const previousMarker = process.env.COWORK_MARKER;
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
    restore('COWORK_FLOW_PYTHON', previousPython);
    restore('COWORK_MARKER', previousMarker);
    resetWorkingPython();
  });

  // A stub interpreter that records every invocation. The JS-side root
  // pre-check must short-circuit before any interpreter is discovered, so
  // the marker never exists.
  await writeFile(stub, '#!/bin/sh\nprintf x > "$COWORK_MARKER"\n', { mode: 0o755 });
  process.env.COWORK_FLOW_PYTHON = stub;
  process.env.COWORK_MARKER = marker;
  resetWorkingPython();

  assert.equal(await runWorkflowState(join(dir, 'sub')), '');
  // Second call exercises the negative cache; still no interpreter.
  assert.equal(await runWorkflowState(join(dir, 'sub')), '');
  await assert.rejects(access(marker));

  function restore(name, value) {
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
});


test('findCoworkRoot climbs to the nearest cowork-flow root', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'cowork-flow-root-'));
  const outside = await mkdtemp(join(tmpdir(), 'cowork-flow-outside-'));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
    await rm(outside, { recursive: true, force: true });
  });

  await mkdir(join(root, '.cowork-flow'), { recursive: true });
  await mkdir(join(root, 'a', 'b'), { recursive: true });

  assert.equal(await findCoworkRoot(join(root, 'a', 'b')), root);
  assert.equal(await findCoworkRoot(root), root);
  assert.equal(await findCoworkRoot(outside), null);
});


test('isLifecycleCommand recognises workflow lifecycle invocations', () => {
  assert.equal(
    isLifecycleCommand('cd E:\\proj && ./.cowork-flow/run task next --json'),
    true,
  );
  assert.equal(
    isLifecycleCommand({ command: './.cowork-flow/run subagent bind rtx-1 key-1' }),
    true,
  );
  assert.equal(
    isLifecycleCommand('.cowork-flow\\run.cmd task next --run'),
    true,
  );
  assert.equal(isLifecycleCommand('python tests/demo.py'), false);
  assert.equal(isLifecycleCommand('git status --short'), false);
  assert.equal(isLifecycleCommand(''), false);
  assert.equal(isLifecycleCommand(undefined), false);
  assert.equal(isLifecycleCommand(null), false);
  assert.equal(isLifecycleCommand(42), false);
});
