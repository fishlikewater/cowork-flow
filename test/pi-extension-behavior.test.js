import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';

import { templateRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);
const EXTENSION_SOURCE = join(templateRoot, '.pi', 'extensions', 'cowork-flow.ts');


async function tempDir(t, prefix) {
  const dir = await mkdtemp(join(tmpdir(), prefix));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}


// The extension is plain JavaScript in a `.ts` file (Pi loads `.ts` itself).
// Copying it to `.mjs` lets plain Node import and execute the real module, so
// these cases cover the before_agent_start transport, not its source text.
async function loadExtension(t) {
  const dir = await tempDir(t, 'cowork-flow-pi-ext-');
  const modulePath = join(dir, 'cowork-flow.mjs');
  await copyFile(EXTENSION_SOURCE, modulePath);
  const module = await import(pathToFileURL(modulePath).href);
  const handlers = new Map();
  module.default({ on: (name, handler) => handlers.set(name, handler) });
  const handler = handlers.get('before_agent_start');
  assert.equal(typeof handler, 'function', 'extension must register before_agent_start');
  return handler;
}


// A stub project: `.cowork-flow/` marks the workflow root, and `inject.py` is
// executed by Node (COWORK_FLOW_PYTHON=process.execPath) so the case needs no
// Python interpreter. It records every call and echoes FAKE_CONTEXT back.
async function stubProject(t, { exitCode = 0 } = {}) {
  const root = await tempDir(t, 'cowork-flow-pi-proj-');
  const scripts = join(root, '.cowork-flow', 'scripts', 'adapters', 'host');
  await mkdir(scripts, { recursive: true });
  const calls = join(root, 'calls.jsonl');
  const source = [
    "const fs = require('node:fs');",
    'let raw = "";',
    "process.stdin.setEncoding('utf8');",
    "process.stdin.on('data', (chunk) => { raw += chunk; });",
    "process.stdin.on('end', () => {",
    `  fs.appendFileSync(${JSON.stringify(calls)}, raw + '\\n');`,
    `  if (${exitCode} !== 0) { process.exit(${exitCode}); }`,
    "  const context = process.env.FAKE_CONTEXT || '';",
    '  process.stdout.write(JSON.stringify({',
    "    hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: context }",
    '  }));',
    '});'
  ].join('\n');
  await writeFile(join(scripts, 'inject.py'), source, 'utf8');
  return { root, calls };
}


async function calls(callsPath) {
  try {
    const text = await readFile(callsPath, 'utf8');
    return text.split('\n').filter(Boolean).map((line) => JSON.parse(line));
  } catch {
    return [];
  }
}


function contextFor(cwd, id = 'sess-1') {
  return { cwd, sessionManager: { getSessionId: () => id } };
}


async function withNodeAsPython(env, run) {
  const previousPython = process.env.COWORK_FLOW_PYTHON;
  const previousContext = process.env.FAKE_CONTEXT;
  const previousSession = process.env.PI_SESSION_ID;
  process.env.COWORK_FLOW_PYTHON = process.execPath;
  process.env.FAKE_CONTEXT = env.context;
  delete process.env.PI_SESSION_ID;
  try {
    return await run();
  } finally {
    const restore = (name, value) => {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    };
    restore('COWORK_FLOW_PYTHON', previousPython);
    restore('FAKE_CONTEXT', previousContext);
    restore('PI_SESSION_ID', previousSession);
  }
}


test('injects the rendered context once and labels the first call SessionStart', async (t) => {
  const handler = await loadExtension(t);
  const project = await stubProject(t);

  const first = await withNodeAsPython({ context: '<workflow-state>one</workflow-state>' }, () =>
    handler({ messageType: 'user' }, contextFor(project.root))
  );

  assert.deepEqual(first, {
    message: {
      customType: 'cowork-flow',
      content: '<workflow-state>one</workflow-state>',
      display: false
    }
  });
  const log = await calls(project.calls);
  assert.equal(log.length, 1);
  assert.equal(log[0].hook_event_name, 'SessionStart');
  assert.equal(log[0].PI_SESSION_ID, 'sess-1');
  assert.equal(log[0].cwd, project.root);
  assert.equal(process.env.PI_SESSION_ID, undefined, 'env is restored by the harness');
});


test('skips a repeated payload but emits again after the state changes', async (t) => {
  const handler = await loadExtension(t);
  const project = await stubProject(t);

  const first = await withNodeAsPython({ context: 'same' }, () =>
    handler({ messageType: 'user' }, contextFor(project.root))
  );
  const second = await withNodeAsPython({ context: 'same' }, () =>
    handler({ messageType: 'user' }, contextFor(project.root))
  );
  const third = await withNodeAsPython({ context: 'changed' }, () =>
    handler({ messageType: 'user' }, contextFor(project.root))
  );

  assert.equal(first.message.content, 'same');
  assert.equal(second, undefined, 'an unchanged rendering must not be injected twice');
  assert.equal(third.message.content, 'changed');
  const log = await calls(project.calls);
  // The first turn is SessionStart, every later turn is UserPromptSubmit.
  assert.deepEqual(
    log.map((entry) => entry.hook_event_name),
    ['SessionStart', 'UserPromptSubmit', 'UserPromptSubmit']
  );
});


test('ignores runs started by another custom message', async (t) => {
  const handler = await loadExtension(t);
  const project = await stubProject(t);

  const result = await withNodeAsPython({ context: 'x' }, () =>
    handler({ messageType: 'custom' }, contextFor(project.root))
  );

  assert.equal(result, undefined);
  assert.deepEqual(await calls(project.calls), []);
});


test('stays silent outside a cowork-flow project', async (t) => {
  const handler = await loadExtension(t);
  const plain = await tempDir(t, 'cowork-flow-pi-plain-');

  const result = await withNodeAsPython({ context: 'x' }, () =>
    handler({ messageType: 'user' }, contextFor(plain))
  );

  assert.equal(result, undefined);
  assert.deepEqual(await readdir(plain), []);
});


test('a failing inject entry never blocks the run', async (t) => {
  const handler = await loadExtension(t);
  const project = await stubProject(t, { exitCode: 3 });

  const result = await withNodeAsPython({ context: 'x' }, () =>
    handler({ messageType: 'user' }, contextFor(project.root))
  );

  assert.equal(result, undefined);
  assert.equal((await calls(project.calls)).length, 1, 'the entry was still invoked');
});


test('the packaged extension is the installer payload', async (t) => {
  // `cwf host add pi` copies this exact file; the behavior cases above import
  // the same path, so a rename here would break both at once.
  const source = await readFile(EXTENSION_SOURCE, 'utf8');
  assert.ok(source.includes('CoworkFlowPiExtension'));
  const agentDir = await tempDir(t, 'cowork-flow-pi-agent-');
  const result = await execFileAsync(process.execPath, [
    join(templateRoot, '..', 'bin', 'cowork-flow.js'),
    'host', 'add', 'pi'
  ], { env: { ...process.env, PI_CODING_AGENT_DIR: agentDir } });
  assert.equal(result.stderr, '');
  assert.equal(
    (await readFile(join(agentDir, 'extensions', 'cowork-flow.ts'), 'utf8')),
    source
  );
});
