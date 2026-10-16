import assert from "node:assert/strict"
import { cpSync } from "node:fs"
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { test } from "node:test"
import { pathToFileURL } from "node:url"

import "./helpers/bytecode-isolation.js"
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
const TEMPLATE_SCRIPTS = join(packageRoot, "template", ".cowork-flow", "scripts")

// The transform spawns the Python runtime with this process's environment; a
// developer running the suite inside a bound cowork-flow session has
// COWORK_FLOW_* set, and the env layer outranks the hook payload, so every
// render here runs with those variables removed (plus any test overrides).
async function withScrubbedEnv(overrides, fn) {
  const saved = {}
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("COWORK_FLOW_")) {
      saved[key] = process.env[key]
      delete process.env[key]
    }
  }
  Object.assign(process.env, overrides)
  try {
    return await fn()
  } finally {
    for (const key of Object.keys(process.env)) {
      if (key.startsWith("COWORK_FLOW_")) {
        delete process.env[key]
      }
    }
    Object.assign(process.env, saved)
  }
}

// A fixture with the Python runtime installed the way init/sync would install
// it: the transform's render path is the real inject.py over the fixture's own
// registry, so the assertions below pin the Python output, not a JS re-read.
async function createRegistryRepo(t) {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-plugin-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })

  const specDir = join(root, ".cowork-flow", "spec")
  await mkdir(specDir, { recursive: true })
  await mkdir(join(specDir, "runtime"), { recursive: true })
  await mkdir(join(specDir, "contracts"), { recursive: true })
  cpSync(TEMPLATE_SCRIPTS, join(root, ".cowork-flow", "scripts"), { recursive: true })
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

// A fixture whose inject.py is a fake that echoes its argv and stdin payload,
// so the transport contract (what the shim forwards, what it does with stdout)
// is tested without involving the Python runtime.
const FAKE_INJECT = [
  "import json, sys",
  "payload = json.load(sys.stdin)",
  'print("SHIM_SENTINEL " + json.dumps({"argv": sys.argv[1:], "payload": payload}, sort_keys=True))',
  "",
].join("\n")

async function createShimRepo(t, script = FAKE_INJECT) {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-shim-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })
  const injectDir = join(root, ".cowork-flow", "scripts", "adapters", "host")
  await mkdir(injectDir, { recursive: true })
  await writeFile(join(injectDir, "inject.py"), script, "utf8")
  return root
}

async function renderPluginContext(cwd, input = {}, envOverrides = {}) {
  const plugin = await CoworkFlowPlugin()
  const output = { system: [] }
  await withScrubbedEnv(envOverrides, () =>
    plugin["experimental.chat.system.transform"]({ cwd, ...input }, output)
  )
  return output
}

async function renderContextText(cwd, input = {}) {
  const output = await renderPluginContext(cwd, input)
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

// The shim forwards render failures to the host log through console.error
// (zcode shim parity); tests capture that channel to pin the diagnostics.
async function captureConsoleError(fn) {
  const lines = []
  const original = console.error
  console.error = (...args) => {
    lines.push(args.map(String).join(" "))
  }
  try {
    const result = await fn()
    return { result, lines }
  } finally {
    console.error = original
  }
}

function extractFingerprint(context) {
  const match = context.match(/<contract-digest fingerprint="([^"]+)">/)
  assert.ok(match, "expected contract digest fingerprint")
  return match[1]
}

test("transform forwards the event to inject.py and injects its stdout", async (t) => {
  const root = await createShimRepo(t)

  const output = await renderPluginContext(root, { sessionID: "child-session", prompt: "hello" })

  assert.equal(output.system.length, 1)
  const text = output.system[0]
  assert.ok(text.startsWith("SHIM_SENTINEL "), `expected the fake script stdout, got: ${text}`)
  const echoed = JSON.parse(text.slice("SHIM_SENTINEL ".length))
  assert.deepEqual(echoed.argv, ["--host", "opencode"])
  assert.equal(echoed.payload.hook_event_name, "UserPromptSubmit")
  assert.equal(echoed.payload.cwd, root)
  // Host input keys ride the payload unchanged: the Python identity table
  // (session ids, runtime-context keys, prompt) resolves them downstream.
  assert.equal(echoed.payload.sessionID, "child-session")
  assert.equal(echoed.payload.prompt, "hello")
})

test("transform stays silent when no inject.py is resolvable", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "cowork-flow-opencode-empty-"))
  t.after(async () => {
    await rm(root, { recursive: true, force: true })
  })
  await mkdir(join(root, ".cowork-flow"), { recursive: true })

  const output = await renderPluginContext(root)

  assert.deepEqual(output.system, [])
})

test("transform skips injection but forwards diagnostics when inject.py fails", async (t) => {
  const root = await createShimRepo(
    t,
    "import sys\nsys.stderr.write('BOOM-DIAGNOSTIC\\n')\nsys.exit(3)\n"
  )

  const { result: output, lines } = await captureConsoleError(() =>
    renderPluginContext(root)
  )

  assert.deepEqual(output.system, [])
  const log = lines.join("\n")
  assert.ok(log.includes("BOOM-DIAGNOSTIC"), `expected child stderr in the host log, got: ${log}`)
  assert.ok(
    log.includes("inject.py exited 3; skipping injection"),
    `expected the skip diagnostic in the host log, got: ${log}`
  )
})

test("transform kills a stuck render instead of holding the prompt", async (t) => {
  const root = await createShimRepo(t, "import time\ntime.sleep(60)\n")

  const started = Date.now()
  const { result: output, lines } = await captureConsoleError(() =>
    renderPluginContext(root)
  )
  const elapsed = Date.now() - started

  assert.deepEqual(output.system, [])
  assert.ok(
    elapsed < 30000,
    `expected the shim timeout to bound the wait well under the 60s sleep, took ${elapsed}ms`
  )
  assert.ok(
    lines.join("\n").includes("inject.py timed out; skipping injection"),
    `expected the timeout diagnostic in the host log, got: ${lines.join("\n")}`
  )
})

test("an interpreter candidate that never starts logs no skip diagnostic", async (t) => {
  const root = await createShimRepo(t)

  const { result: output, lines } = await captureConsoleError(() =>
    renderPluginContext(root, {}, { COWORK_FLOW_PYTHON: "cowork-flow-missing-python-9x" })
  )

  assert.equal(
    output.system.length,
    1,
    `expected a later interpreter candidate to render, got: ${JSON.stringify(output.system)}`
  )
  assert.ok(
    !lines.join("\n").includes("skipping injection"),
    `expected no skip diagnostic for a never-started candidate, got: ${lines.join("\n")}`
  )
})

test("transform honors the COWORK_FLOW_HOOKS kill switch", async (t) => {
  const root = await createShimRepo(t)

  const output = await renderPluginContext(root, {}, { COWORK_FLOW_HOOKS: "0" })

  assert.deepEqual(output.system, [])
})

test("opencode plugin injects registry-driven contract digest", async (t) => {
  const root = await createRegistryRepo(t)

  const context = await renderContextText(root)

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
  cpSync(TEMPLATE_SCRIPTS, join(root, ".cowork-flow", "scripts"), { recursive: true })

  const context = await renderContextText(root)

  assert.match(context, /warning: contract registry unavailable/)
  assert.match(context, /using fallback digest/)
})

test("opencode plugin fingerprint changes when referenced spec changes", async (t) => {
  const root = await createRegistryRepo(t)

  const before = await renderContextText(root)
  await writeFile(
    join(root, ".cowork-flow", "spec", "contracts", "test-contract.md"),
    "FULL_SPEC_SENTINEL changed body that still must not be injected.\n",
    "utf8"
  )
  const after = await renderContextText(root)

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

  const context = await renderContextText(root, {
    opencode_session_id: "child-session",
    prompt: "cowork_runtime_context_id: rtx_plugin\ncowork_host_context_key: opencode_prompt_key",
  })

  assert.match(context, /status="delegated_subtask"/)
  assert.match(context, /source="runtime-context:rtx_plugin"/)
  assert.match(context, /Agent: cowork-check/)
  // Scope ownership moved into the stage-contract block: "Scope: subagent"
  // lines are gone; absent task artifacts render no block at all.
  assert.doesNotMatch(context, /Scope: subagent/)
  // The bind is the Python storage layer's write: one session record keyed by
  // the host context key, and the runtime context flipped to bound.
  const session = JSON.parse(
    await readFile(
      join(root, ".cowork-flow", ".runtime", "sessions", "opencode_prompt_key.json"),
      "utf8"
    )
  )
  assert.equal(session.scope, "subagent")
  assert.equal(session.runtime_context_id, "rtx_plugin")
  assert.equal(session.platform, "opencode")
  assert.equal(session.status, "bound")
  assert.equal(session._state.schema_version, 1)
  assert.equal(Number.isInteger(session._state.revision), true)
  await assert.rejects(
    readFile(join(root, ".cowork-flow", ".runtime", "sessions", "opencode_child-session.json"), "utf8")
  )
  const runtimeContext = JSON.parse(
    await readFile(join(root, ".cowork-flow", ".runtime", "subagents", "rtx_plugin.json"), "utf8")
  )
  assert.equal(runtimeContext.status, "bound")
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

  // The host is not contractually obliged to hand a config at all.
  await payloadHooks.config(undefined)
  await payloadHooks.config(null)
})
