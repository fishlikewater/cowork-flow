import assert from "node:assert/strict"
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { execFileSync } from "node:child_process"
import { test } from "node:test"

import { CoworkFlowPlugin } from "../template/.opencode/plugins/cowork-flow.js"

async function createRegistryRepo(t) {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-plugin-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })

  const specDir = join(root, ".cowork-flow", "spec")
  await mkdir(specDir, { recursive: true })
  await writeFile(
    join(specDir, "registry.json"),
    JSON.stringify(
      {
        schemaVersion: 1,
        contracts: [
          {
            id: "TEST_CONTRACT_V1",
            path: ".cowork-flow/spec/test-contract.md",
            digest: ["Short registry digest.", "Second short registry digest."],
            readWhen: ["before test action", "when test conflict exists"],
          },
        ],
      },
      null,
      2
    ),
    "utf8"
  )
  await writeFile(
    join(specDir, "test-contract.md"),
    "FULL_SPEC_SENTINEL initial body that must not be injected.\n",
    "utf8"
  )
  return root
}

async function createRuntimeRepo(t) {
  const root = await createRegistryRepo(t)
  const workflowRoot = join(root, ".cowork-flow")
  await mkdir(join(workflowRoot, "scripts"), { recursive: true })
  await mkdir(join(workflowRoot, "tasks", "06-04-demo"), { recursive: true })
  await writeFile(join(workflowRoot, "scripts", "run.py"), "placeholder\n", "utf8")
  execFileSync(
    process.execPath,
    [
      "-e",
      "import { cpSync } from 'node:fs'; cpSync(process.argv[1], process.argv[2], { recursive: true })",
      join(process.cwd(), ".cowork-flow", "scripts", "flow"),
      join(workflowRoot, "scripts", "flow"),
    ],
    { encoding: "utf8" }
  )
  execFileSync(
    process.execPath,
    [
      "-e",
      "import { cpSync } from 'node:fs'; cpSync(process.argv[1], process.argv[2], { recursive: true })",
      join(process.cwd(), ".cowork-flow", "scripts", "common"),
      join(workflowRoot, "scripts", "common"),
    ],
    { encoding: "utf8" }
  )
  execFileSync(
    process.execPath,
    [
      "-e",
      "import { cpSync } from 'node:fs'; cpSync(process.argv[1], process.argv[2], { recursive: true })",
      join(process.cwd(), ".cowork-flow", "scripts", "patterns"),
      join(workflowRoot, "scripts", "patterns"),
    ],
    { encoding: "utf8" }
  )
  return root
}

function flowStoreEval(root, code) {
  return execFileSync(
    process.env.PYTHON || "python3",
    [
      "-c",
      [
        "import json, sys",
        "from pathlib import Path",
        "root = Path(sys.argv[1])",
        "sys.path.insert(0, str(root / '.cowork-flow' / 'scripts'))",
        "from flow.store import FlowStore",
        "from common.paths import FILE_FLOW_DB",
        "db = root / '.cowork-flow' / FILE_FLOW_DB",
        "with FlowStore(str(db)) as store:",
        ...code.map((line) => `    ${line}`),
      ].join("\n"),
      root,
    ],
    {
      encoding: "utf8",
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    }
  )
}

async function renderPluginContext(cwd, input = {}) {
  const plugin = await CoworkFlowPlugin()
  const output = { system: [] }
  await plugin["experimental.chat.system.transform"]({ cwd, ...input }, output)
  assert.equal(output.system.length, 1)
  return output.system[0]
}

async function renderShellEnv(cwd, input = {}) {
  const plugin = await CoworkFlowPlugin()
  assert.equal(typeof plugin["shell.env"], "function")
  const output = { env: {} }
  await plugin["shell.env"]({ cwd, ...input }, output)
  return output.env
}

function extractFingerprint(context) {
  const match = context.match(/<contract-digest fingerprint="([^"]+)">/)
  assert.ok(match, "expected contract digest fingerprint")
  return match[1]
}

test("opencode plugin injects registry-driven contract digest", async (t) => {
  const root = await createRegistryRepo(t)

  const context = await renderPluginContext(root)

  assert.match(context, /<cowork-runtime host="opencode" adapter="opencode\.task">/)
  assert.match(context, /<contract-digest fingerprint="[a-f0-9]{16}">/)
  assert.match(context, /<opencode-entry-signals>/)
  assert.match(context, /sessionRole: main/)
  assert.match(context, /invocationKind: interactive/)
  assert.match(context, /- TEST_CONTRACT_V1: \.cowork-flow\/spec\/test-contract\.md/)
  assert.match(context, /digest: Short registry digest\./)
  assert.match(context, /read_before: before test action; when test conflict exists/)
  assert.doesNotMatch(context, /FULL_SPEC_SENTINEL/)
})

test("opencode plugin fingerprint changes when referenced spec changes", async (t) => {
  const root = await createRegistryRepo(t)

  const before = await renderPluginContext(root)
  await writeFile(
    join(root, ".cowork-flow", "spec", "test-contract.md"),
    "FULL_SPEC_SENTINEL changed body that still must not be injected.\n",
    "utf8"
  )
  const after = await renderPluginContext(root)

  assert.notEqual(extractFingerprint(before), extractFingerprint(after))
  assert.doesNotMatch(after, /FULL_SPEC_SENTINEL/)
})

test("opencode plugin injects and binds runtime subagent state", async (t) => {
  const root = await createRuntimeRepo(t)
  flowStoreEval(root, [
    "store.upsert_runtime_context({",
    "  'runtime_context_id': 'rtx_plugin',",
    "  'scope': 'subagent',",
    "  'host': 'opencode',",
    "  'adapter': 'opencode.task',",
    "  'agent_type': 'cowork-check',",
    "  'role': 'check',",
    "  'task_dir': '.cowork-flow/tasks/06-04-demo',",
    "  'status': 'pending',",
    "  'assignment': {'goal': 'Check the runtime binding.'},",
    "  'bound_context_key': None,",
    "})",
  ])

  const context = await renderPluginContext(root, {
    opencode_session_id: "child-session",
    prompt: "cowork_runtime_context_id: rtx_plugin\ncowork_host_context_key: opencode_prompt_key",
  })

  assert.match(context, /sessionRole: command/)
  assert.match(context, /Status: delegated_subtask/)
  assert.match(context, /Source: runtime-context:rtx_plugin/)
  assert.match(context, /Agent: cowork-check/)
  assert.match(context, /Scope: subagent/)
  const session = JSON.parse(
    flowStoreEval(root, [
      "session = store.get_runtime_session('opencode_prompt_key')",
      "print(json.dumps(session, ensure_ascii=False, sort_keys=True))",
    ])
  )
  assert.equal(session.scope, "subagent")
  assert.equal(session.runtime_context_id, "rtx_plugin")
  await assert.rejects(
    readFile(join(root, ".cowork-flow", ".runtime", "sessions", "opencode_child-session.json"), "utf8")
  )
  await assert.rejects(
    readFile(join(root, ".cowork-flow", ".runtime", "sessions", "opencode_prompt_key.json"), "utf8")
  )
  await assert.rejects(
    readFile(join(root, ".cowork-flow", ".runtime", "subagents", "rtx_plugin.json"), "utf8")
  )
  const runtimeContext = JSON.parse(
    flowStoreEval(root, [
      "context = store.get_runtime_context('rtx_plugin')",
      "print(json.dumps(context, ensure_ascii=False, sort_keys=True))",
    ])
  )
  assert.equal(runtimeContext.bound_context_key, "opencode_prompt_key")
})

test("opencode plugin fails closed for closed runtime context", async (t) => {
  const root = await createRuntimeRepo(t)
  flowStoreEval(root, [
    "store.upsert_runtime_context({",
    "  'runtime_context_id': 'rtx_closed_plugin',",
    "  'scope': 'subagent',",
    "  'host': 'opencode',",
    "  'adapter': 'opencode.task',",
    "  'agent_type': 'cowork-check',",
    "  'role': 'check',",
    "  'task_dir': '.cowork-flow/tasks/06-04-demo',",
    "  'status': 'closed',",
    "  'assignment': {'goal': 'Check the runtime binding.'},",
    "  'bound_context_key': None,",
    "})",
  ])

  const context = await renderPluginContext(root, {
    opencode_session_id: "child-session",
    prompt: "cowork_runtime_context_id: rtx_closed_plugin",
  })

  assert.match(context, /Status: delegated_subtask/)
  assert.match(context, /runtime-context-invalid:rtx_closed_plugin/)
  assert.match(context, /Runtime context is missing, closed, or invalid/)
  assert.match(context, /Do not run start\/resume\/task start\/archive\/commit\/spawn\./)
})

test("opencode plugin exposes main session env to shell commands", async (t) => {
  const root = await createRegistryRepo(t)

  const env = await renderShellEnv(root, { sessionID: "main session" })

  assert.equal(env.SESSIONROLE, "main")
  assert.equal(env.INVOCATIONKIND, "interactive")
  assert.equal(env.COWORK_FLOW_CONTEXT_ID, "opencode_main_session")
  assert.equal(env.OPENCODE_SESSION_ID, "main_session")
})

test("opencode party mode v2 command points to runtime board", async () => {
  for (const path of [
    new URL("../template/.opencode/commands/party-mode-v2.md", import.meta.url),
  ]) {
    const text = await readFile(path, "utf8")
    assert.match(text, /Party Mode V2 is advisory only/)
    assert.match(text, /party-v2 init/)
    assert.match(text, /party-v2 monitor/)
    assert.match(text, /party-v2 view/)
    assert.match(text, /party-v2 post/)
    assert.match(text, /party-v2 respond/)
    assert.match(text, /party-v2 advance/)
    assert.match(text, /party-v2 finalize/)
    assert.match(text, /current-round board API/)
    assert.doesNotMatch(text, /forward, summarize, or rewrite child opinions as moderator work/)
    assert.doesNotMatch(text, /spawn_agent|wait_agent|close_agent|codex exec/)
  }
})
