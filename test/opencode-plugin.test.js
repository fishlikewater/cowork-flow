import assert from "node:assert/strict"
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"

import { CoworkFlowPlugin } from "../.opencode/plugins/cowork-flow.js"

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

async function renderPluginContext(cwd, input = {}) {
  const plugin = await CoworkFlowPlugin()
  const output = { system: [] }
  await plugin["experimental.chat.system.transform"]({ cwd, ...input }, output)
  assert.equal(output.system.length, 1)
  return output.system[0]
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
  const root = await createRegistryRepo(t)
  const runtimeDir = join(root, ".cowork-flow", ".runtime", "subagents")
  await mkdir(runtimeDir, { recursive: true })
  await writeFile(
    join(runtimeDir, "rtx_plugin.json"),
    JSON.stringify(
      {
        schema_version: 2,
        runtime_context_id: "rtx_plugin",
        scope: "subagent",
        host: "opencode",
        adapter: "opencode.task",
        agent_type: "cowork-check",
        role: "check",
        task_dir: ".cowork-flow/tasks/06-04-demo",
        status: "pending",
        assignment: { goal: "Check the runtime binding." },
        bound_context_key: null,
      },
      null,
      2
    ),
    "utf8"
  )

  const context = await renderPluginContext(root, {
    opencode_session_id: "child-session",
    prompt: "cowork_runtime_context_id: rtx_plugin",
  })

  assert.match(context, /Status: delegated_subtask/)
  assert.match(context, /Source: runtime-context:rtx_plugin/)
  assert.match(context, /Agent: cowork-check/)
  assert.match(context, /Scope: subagent/)
  const session = JSON.parse(
    await readFile(
      join(root, ".cowork-flow", ".runtime", "sessions", "opencode_child-session.json"),
      "utf8"
    )
  )
  assert.equal(session.scope, "subagent")
  assert.equal(session.runtime_context_id, "rtx_plugin")
})
