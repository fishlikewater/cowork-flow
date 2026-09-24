import assert from "node:assert/strict"
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"
import { pathToFileURL } from "node:url"

import { packageRoot } from "../src/lib/paths.js"
import { CoworkFlowPlugin } from "../template/.opencode/plugins/cowork-flow.js"

// The same plugin is delivered twice: into a project by init/sync, and into the
// machine's OpenCode config directory by `host add opencode`. Both are the same
// source, so every gate below runs against both — a fix applied to one copy only
// is exactly the drift these gates exist to catch.
const PROJECT_PLUGIN = join(packageRoot, "template", ".opencode", "plugins", "cowork-flow.js")
const PROJECT_CORE = join(packageRoot, "template", ".opencode", "cowork-flow", "plugin-core.js")
const PAYLOAD_ROOT = join(packageRoot, "presets", "opencode")
const PAYLOAD_PLUGIN = join(PAYLOAD_ROOT, "plugins", "cowork-flow.js")
const PAYLOAD_CORE = join(PAYLOAD_ROOT, "cowork-flow", "plugin-core.js")
const PLUGIN_MODULES = [PROJECT_PLUGIN, PAYLOAD_PLUGIN].map((file) => pathToFileURL(file).href)
const PLUGIN_MODULE = PLUGIN_MODULES[0]

async function createRegistryRepo(t) {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-plugin-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })

  const specDir = join(root, ".cowork-flow", "spec")
  await mkdir(specDir, { recursive: true })
  await mkdir(join(specDir, "runtime"), { recursive: true })
  await mkdir(join(specDir, "contracts"), { recursive: true })
  const registryContent = JSON.stringify(
    {
      schemaVersion: 1,
      contracts: [
        {
          id: "TEST_CONTRACT_V1",
          path: ".cowork-flow/spec/contracts/test-contract.md",
          digest: ["Short registry digest.", "Second short registry digest."],
          readWhen: ["before test action", "when test conflict exists"],
        },
      ],
    },
    null,
    2
  )
  await writeFile(
    join(root, ".cowork-flow", "spec", "runtime", "contract-registry.json"),
    registryContent,
    "utf8"
  )
  await writeFile(
    join(root, ".cowork-flow", "spec", "contracts", "test-contract.md"),
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
  assert.match(context, /- TEST_CONTRACT_V1: \.cowork-flow\/spec\/contracts\/test-contract\.md/)
  assert.match(context, /digest: Short registry digest\./)
  assert.match(context, /read_before: before test action; when test conflict exists/)
  assert.doesNotMatch(context, /FULL_SPEC_SENTINEL/)
})

test("opencode plugin surfaces registry warning when missing", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-plugin-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })
  await mkdir(join(root, ".cowork-flow", "spec"), { recursive: true })

  const context = await renderPluginContext(root)

  assert.match(context, /warning: contract registry unavailable or invalid/)
  assert.match(context, /using fallback digest/)
})

test("opencode plugin fingerprint changes when referenced spec changes", async (t) => {
  const root = await createRegistryRepo(t)

  const before = await renderPluginContext(root)
  await writeFile(
    join(root, ".cowork-flow", "spec", "contracts", "test-contract.md"),
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
  const runtimeContextContent = JSON.stringify(
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
  )
  await writeFile(join(runtimeDir, "rtx_plugin.json"), runtimeContextContent, "utf8")

  const context = await renderPluginContext(root, {
    opencode_session_id: "child-session",
    prompt: "cowork_runtime_context_id: rtx_plugin\ncowork_host_context_key: opencode_prompt_key",
  })

  assert.match(context, /status="delegated_subtask"/)
  assert.match(context, /source="runtime-context:rtx_plugin"/)
  assert.match(context, /Agent: cowork-check/)
  // Scope ownership moved into the stage-contract block: "Scope: subagent"
  // lines are gone; absent task artifacts render no block at all.
  assert.doesNotMatch(context, /Scope: subagent/)
  const session = JSON.parse(
    await readFile(
      join(root, ".cowork-flow", ".runtime", "sessions", "opencode_prompt_key.json"),
      "utf8"
    )
  )
  assert.equal(session.scope, "subagent")
  assert.equal(session.runtime_context_id, "rtx_plugin")
  await assert.rejects(
    readFile(join(root, ".cowork-flow", ".runtime", "sessions", "opencode_child-session.json"), "utf8")
  )
  const runtimeContext = JSON.parse(
    await readFile(join(root, ".cowork-flow", ".runtime", "subagents", "rtx_plugin.json"), "utf8")
  )
  assert.equal(runtimeContext.bound_context_key, "opencode_prompt_key")
})

test("opencode plugin exposes main session env to shell commands", async (t) => {
  const root = await createRegistryRepo(t)

  const env = await renderShellEnv(root, { sessionID: "main session" })

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

async function runToolExecuteAfter(cwd, input, output = {}) {
  const plugin = await CoworkFlowPlugin()
  assert.equal(typeof plugin["tool.execute.after"], "function")
  await plugin["tool.execute.after"]({ cwd, ...input }, output)
  return output
}

test("tool.execute.after leaves non-edit tools untouched", async (t) => {
  const root = await createRegistryRepo(t)
  const output = await runToolExecuteAfter(root, {
    tool: "bash",
    args: { command: "ls" },
  })
  assert.equal(output.output, undefined)
})

test("tool.execute.after skips an edit without a file path", async (t) => {
  const root = await createRegistryRepo(t)
  const output = await runToolExecuteAfter(
    root,
    { tool: "edit", args: {} },
    { output: "original" }
  )
  assert.equal(output.output, "original")
})

test("tool.execute.after preserves tool output when the runtime is absent", async (t) => {
  const root = await createRegistryRepo(t)
  // The fixture has no .cowork-flow/run entry, so the checker must stay
  // silent instead of failing the edit path.
  const output = await runToolExecuteAfter(
    root,
    { tool: "edit", args: { filePath: "src/a.py" } },
    { output: "original" }
  )
  assert.equal(output.output, "original")
})

// opencode walks every export of a plugin module and calls each one as a plugin
// factory, then iterates the returned hooks objects. A non-function export
// throws inside that loop, and a factory that returns undefined or null makes
// the later `hook["event"]?.(...)` read crash — either way the whole host dies
// during bootstrap, which is what a helper exported for unit tests used to do.
test("opencode plugin module exports only callable factories that return objects", async () => {
  const input = {
    client: {},
    project: {},
    worktree: null,
    directory: packageRoot,
    serverUrl: "http://localhost:4096",
    $: () => {}
  }
  for (const moduleUrl of PLUGIN_MODULES) {
    const module = await import(moduleUrl)
    const names = Object.keys(module)
    assert.ok(names.length > 0, `${moduleUrl} must export at least one factory`)

    for (const name of names) {
      const factory = module[name]
      assert.equal(
        typeof factory,
        "function",
        `export ${name} is not a function; opencode calls every export as a plugin factory`
      )
      const hooks = await factory(input)
      assert.equal(
        typeof hooks,
        "object",
        `export ${name} returned ${hooks === null ? "null" : typeof hooks}; the host iterates the returned hooks object`
      )
      assert.notEqual(hooks, null, `export ${name} returned null`)
    }
  }
})

test("the project copy and the machine payload are byte-identical", async () => {
  // They are one source delivered two ways, and the doctor judges staleness by
  // comparing them — so a difference is either a half-applied change or a
  // spurious PLUGIN-STALE warning. Neither is acceptable silently.
  for (const [project, payload] of [[PROJECT_PLUGIN, PAYLOAD_PLUGIN], [PROJECT_CORE, PAYLOAD_CORE]]) {
    assert.equal(
      await readFile(project, "utf8"),
      await readFile(payload, "utf8"),
      `${project} and ${payload} must stay the same file`
    )
  }
})

test("the config hook registers the payload skills directory, and only when it exists", async () => {
  const projectHooks = await (await import(PLUGIN_MODULES[0])).CoworkFlowPlugin({ directory: packageRoot })
  const payloadHooks = await (await import(PLUGIN_MODULES[1])).CoworkFlowPlugin({ directory: packageRoot })

  // The project copy has no skills/ sibling: registering a path that is not
  // there would only produce a host warning, so it must stay a no-op.
  const projectConfig = {}
  await projectHooks.config(projectConfig)
  assert.equal(projectConfig.skills, undefined)

  const config = {}
  await payloadHooks.config(config)
  const registered = config.skills.paths
  assert.equal(registered.length, 1)
  // The path is derived from the plugin's own file location, not from the
  // session directory or the environment: that is what makes a machine install
  // work in a repository that has no cowork-flow runtime.
  assert.equal(registered[0], join(PAYLOAD_ROOT, "cowork-flow", "skills"))
  await access(join(registered[0], "cowork-flow-bootstrap", "SKILL.md"))

  // A user's own paths survive, and a second load does not append a duplicate.
  const existing = { skills: { paths: ["/somewhere-else"] } }
  await payloadHooks.config(existing)
  await payloadHooks.config(existing)
  assert.deepEqual(existing.skills.paths, ["/somewhere-else", registered[0]])

  // A config the schema would reject must not become a host crash: a plugin that
  // throws here takes the whole process down during bootstrap.
  const malformed = { skills: "not-an-object" }
  await payloadHooks.config(malformed)
  assert.deepEqual(malformed.skills.paths, [registered[0]])
})
