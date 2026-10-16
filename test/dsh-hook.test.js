import assert from 'node:assert/strict';
import { access, cp, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import { apply, editedFilePath, findCoworkRoot, isLifecycleCommand, resetWorkingPython, runEditScopeCheck, runWorkflowState } from '../presets/dsh/plugins/workflow-state.js';
import { packageRoot } from '../src/lib/paths.js';

// The workflow runtime under the repository root is a gitignored live
// checkout (source-refresh), so CI checkouts do not have it. Every test that
// needs a real workflow project builds one from the committed template.
async function createWorkflowProject(t) {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-dsh-hook-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  const workflow = join(dir, '.cowork-flow');
  await mkdir(workflow, { recursive: true });
  await cp(
    join(packageRoot, 'template', '.cowork-flow', 'scripts'),
    join(workflow, 'scripts'),
    { recursive: true }
  );
  await mkdir(join(workflow, 'spec', 'contracts'), { recursive: true });
  await mkdir(join(workflow, 'spec', 'runtime'), { recursive: true });
  await cp(
    join(
      packageRoot,
      'template',
      '.cowork-flow',
      'spec',
      'contracts',
      'workflow-state-templates.md'
    ),
    join(workflow, 'spec', 'contracts', 'workflow-state-templates.md')
  );
  await cp(
    join(
      packageRoot,
      'template',
      '.cowork-flow',
      'spec',
      'runtime',
      'contract-registry.json'
    ),
    join(workflow, 'spec', 'runtime', 'contract-registry.json')
  );
  return dir;
}


test(
  'produces the workflow-state block for a cowork-flow root',
  // Windows' WindowsApps python3 stub runs but serves no protocol, which the
  // interpreter discovery legitimately treats as "interpreter works, protocol
  // failed". Real dsh injection on Windows needs its own fix (product side).
  { skip: process.platform === 'win32' && 'windows python3 stub breaks discovery' },
  async (t) => {
    const project = await createWorkflowProject(t);
    const text = await runWorkflowState(project);

    assert.match(text, /<workflow-state[^>]*>/);
    assert.match(text, /status="[a-z_]+"/);
    assert.match(text, /<cowork-runtime host="dsh"/);
    assert.match(text, /adapter="dsh\.preset\.systemPrompt"/);
  }
);


test('returns empty text outside a cowork-flow root', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-hook-noroot-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  assert.equal(await runWorkflowState(dir), '');
});


test('honours the hook disable switches', async (t) => {
  const project = await createWorkflowProject(t);
  const previousHooks = process.env.COWORK_FLOW_HOOKS;
  const previousDisable = process.env.COWORK_FLOW_DISABLE_HOOKS;
  t.after(() => {
    restore('COWORK_FLOW_HOOKS', previousHooks);
    restore('COWORK_FLOW_DISABLE_HOOKS', previousDisable);
  });

  process.env.COWORK_FLOW_HOOKS = '0';
  assert.equal(await runWorkflowState(project), '');

  delete process.env.COWORK_FLOW_HOOKS;
  process.env.COWORK_FLOW_DISABLE_HOOKS = '1';
  assert.equal(await runWorkflowState(project), '');

  function restore(name, value) {
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
});


test('degrades to empty text when the protocol fails', async (t) => {
  const project = await createWorkflowProject(t);
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
  assert.equal(await runWorkflowState(project), '');

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

function createFakeCtx() {
  const handlers = new Map();
  let section;
  const ctx = {
    on(event, handler) {
      handlers.set(event, handler);
    },
    effect(run) {
      run();
    },
    systemPrompt: {
      section(definition) {
        section = definition;
      }
    }
  };
  return { ctx, handlers, section: () => section };
}


async function waitFor(check, label) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (check()) {
      return;
    }
    await new Promise((resolve) => { setTimeout(resolve, 50); });
  }
  throw new Error('timed out waiting for ' + label);
}


test('apply wires every refresh event and registers the workflow-state section', () => {
  const { ctx, handlers, section } = createFakeCtx();

  apply(ctx);

  // Both start-event names are wired on purpose: 0.2.0 renamed
  // `agent/session-start` to `agent/created`, and each DSH line only emits
  // one of them.
  assert.deepEqual(
    [...handlers.keys()].sort(),
    [
      'agent/created',
      'agent/inbox/claimed',
      'agent/session-start',
      'tools/post-execute',
      'tools/result'
    ]
  );
  const definition = section();
  assert.equal(definition.name, 'cowork-flow-workflow-state');
  assert.equal(definition.order, 1000);
  // No agent has been refreshed yet, so prompt assembly must get an empty
  // section instead of an exception.
  assert.equal(definition.text({ agent: { cwd: process.cwd() } }), '');
  assert.equal(definition.text(undefined), '');
});


test('apply degrades silently when the session cwd is not a cowork-flow root', async (t) => {
  const dir = await mkdtemp(join(tmpdir(), 'cowork-flow-dsh-plain-'));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  const { ctx, handlers, section } = createFakeCtx();
  apply(ctx);
  const agent = { cwd: dir };

  handlers.get('agent/session-start')({ agent });
  await new Promise((resolve) => { setTimeout(resolve, 300); });

  assert.equal(section().text({ agent }), '');
});


test(
  'a session refresh replaces the cached block instead of accumulating',
  // Windows' WindowsApps python3 stub runs but serves no protocol, which the
  // interpreter discovery legitimately treats as "interpreter works, protocol
  // failed". Real dsh injection on Windows needs its own fix (product side).
  { skip: process.platform === 'win32' && 'windows python3 stub breaks discovery' },
  async (t) => {
    const project = await createWorkflowProject(t);
    const { ctx, handlers, section } = createFakeCtx();
    apply(ctx);
    const agent = { cwd: project };
    const sessionStart = handlers.get('agent/session-start');

    sessionStart({ agent });
    await waitFor(() => section().text({ agent }) !== '', 'first workflow-state block');
    const first = section().text({ agent });
    assert.match(first, /<cowork-runtime host="dsh"/);

    sessionStart({ agent });
    await new Promise((resolve) => { setTimeout(resolve, 500); });
    const second = section().text({ agent });

    // The refresh replaces the cached text; a regression that appends would
    // leave two blocks in the next prompt assembly.
    assert.equal((second.match(/<workflow-state/g) ?? []).length, 1);
    assert.match(second, /<cowork-runtime host="dsh"/);
  }
);


// A project with one in-progress task, a single-file whitelist, and the main
// plus subagent session bindings the scope check reads.
async function createScopeProject(t) {
  const dir = await createWorkflowProject(t);
  const taskDir = join(dir, '.cowork-flow', 'tasks', '09-01-demo');
  await mkdir(taskDir, { recursive: true });
  await writeFile(
    join(taskDir, 'task.json'),
    JSON.stringify({ status: 'in_progress' }) + '\n',
    'utf8'
  );
  await writeFile(
    join(taskDir, 'implement.jsonl'),
    JSON.stringify({ file: 'src/child.py', type: 'file' }) + '\n',
    'utf8'
  );
  const sessions = join(dir, '.cowork-flow', '.runtime', 'sessions');
  await mkdir(sessions, { recursive: true });
  for (const [key, scope] of [['dsh_s1', 'main'], ['dsh_child', 'subagent']]) {
    await writeFile(
      join(sessions, `${key}.json`),
      JSON.stringify({
        active_task_path: '.cowork-flow/tasks/09-01-demo',
        scope,
        last_seen_at: '2026-09-08T00:00:00+00:00'
      }) + '\n',
      'utf8'
    );
  }
  return dir;
}


const SCOPE_WARNING = (path) =>
  `⚠️ ${path} is outside the task's declared scope. ` +
  "If intended, declare it in the task's `implement.jsonl` (agent-mutable) " +
  'or revert the edit.';


test('editedFilePath reads only fs edit tools carrying a file path', () => {
  assert.equal(editedFilePath({ name: 'write', arguments: { file_path: 'src/a.py' } }), 'src/a.py');
  assert.equal(editedFilePath({ name: 'edit', arguments: { file_path: '  src/a.py ' } }), 'src/a.py');
  assert.equal(editedFilePath({ name: 'bash', arguments: { file_path: 'src/a.py' } }), '');
  assert.equal(editedFilePath({ name: 'write', arguments: {} }), '');
  assert.equal(editedFilePath(undefined), '');
});


test('runEditScopeCheck reports an out-of-scope edit and stays silent otherwise', async (t) => {
  const project = await createScopeProject(t);
  const previous = process.env.DSH_SESSION_ID;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_SESSION_ID;
    } else {
      process.env.DSH_SESSION_ID = previous;
    }
    resetWorkingPython();
  });

  process.env.DSH_SESSION_ID = 's1';
  resetWorkingPython();
  assert.equal(
    await runEditScopeCheck(project, 'src/outside.py'),
    SCOPE_WARNING('src/outside.py')
  );
  assert.equal(await runEditScopeCheck(project, 'src/child.py'), '');
  assert.equal(await runEditScopeCheck(project, ''), '');

  // A delegated session follows its own slice, so the advisory stays silent
  // there (same rule as zcode's PostToolUse short path).
  process.env.DSH_SESSION_ID = 'child';
  assert.equal(await runEditScopeCheck(project, 'src/outside.py'), '');
});


test('apply merges the edit-scope notice into the finished tool result', async (t) => {
  const project = await createScopeProject(t);
  const previous = process.env.DSH_SESSION_ID;
  t.after(() => {
    if (previous === undefined) {
      delete process.env.DSH_SESSION_ID;
    } else {
      process.env.DSH_SESSION_ID = previous;
    }
    resetWorkingPython();
  });
  process.env.DSH_SESSION_ID = 's1';
  resetWorkingPython();

  const { ctx, handlers } = createFakeCtx();
  apply(ctx);
  const postExecute = handlers.get('tools/post-execute');
  assert.equal(typeof postExecute, 'function');

  // Non-edit tools never spawn the checker, and the downstream decision rides
  // through untouched.
  const untouched = await postExecute(
    { agent: { cwd: project }, name: 'bash', arguments: {} },
    null,
    async () => ({ kind: 'accept', additionalContexts: [{ id: 'downstream' }] })
  );
  assert.deepEqual(untouched, { kind: 'accept', additionalContexts: [{ id: 'downstream' }] });

  // An out-of-scope edit adds one plugin notice ahead of the downstream
  // contexts; the downstream result itself is preserved.
  const result = await postExecute(
    { agent: { cwd: project }, name: 'write', arguments: { file_path: 'src/outside.py' } },
    null,
    async () => ({ kind: 'accept', additionalContexts: [{ id: 'downstream' }] })
  );
  assert.equal(result.kind, 'accept');
  assert.equal(result.additionalContexts.length, 2);
  assert.equal(result.additionalContexts[1].id, 'downstream');
  const notice = result.additionalContexts[0];
  assert.equal(notice.role, 'user');
  assert.equal(notice.source.summary, 'edit-scope');
  assert.equal(notice.content[0].text, SCOPE_WARNING('src/outside.py'));
});

