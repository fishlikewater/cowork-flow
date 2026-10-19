// Transport shim behind the opencode plugin. Every workflow fact
// (contract digest, workflow-state, decision anchor, stage contract,
// runtime-context bind, edit-scope warning) is rendered by the Python
// source <scripts>/adapters/host/inject.py --host opencode; this module
// moves bytes only. What stays here is what the Python side cannot
// reach: the config-hook skills registration, the shell.env context-key
// export, and the tool-shape translation for the tool.execute.after
// edit-scope delegation.
//
// This module must NOT live under plugins/: opencode
// treats every file directly inside plugins/ as a plugin
// and calls every export of it as a plugin factory, so
// library code there kills the host during bootstrap. A
// namespaced sibling directory also keeps the payload tree
// self-similar between a project install and the machine
// install, so the adapter's relative import resolves in
// both.

import { spawn, spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const DIR_WORKFLOW = ".cowork-flow"
// One prompt assembly must not wait longer than a host hook event.
const INJECT_TIMEOUT_MS = 4800
// The .cowork-flow/run floor, reused here: a candidate that cannot run
// Python 3.10+ is skipped like a missing binary, so a stale `python3`
// never hides a working `python` further down the list.
const MIN_PYTHON_CHECK =
  "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"

function interpreterIsUsable(candidate) {
  try {
    const probe = spawnSync(candidate[0], [...candidate.slice(1), "-c", MIN_PYTHON_CHECK], {
      timeout: INJECT_TIMEOUT_MS,
      windowsHide: true,
    })
    // A probe killed by its own timeout reached no verdict — a loaded machine,
    // not a bad interpreter — so let the real spawn decide; it carries the
    // same timeout and its own diagnostics.
    if (probe.error && probe.error.code === "ETIMEDOUT") return true
    return !probe.error && probe.status === 0
  } catch {
    return false
  }
}

// Last-resort repository root: this module lives at
// <payload>/cowork-flow/plugin-core.js, next to plugins/,
// so three levels up is the directory the payload was
// installed into. Used only when no candidate directory
// carries a .cowork-flow/ runtime.
const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..")

function inputCwd(input) {
  for (const value of [
    input?.cwd,
    input?.session?.cwd,
    input?.context?.cwd,
    input?.workspace?.cwd,
  ]) {
    if (typeof value === "string" && value.trim()) {
      return value
    }
  }
  return null
}

function findRepoRoot(input) {
  const candidates = [
    inputCwd(input),
    typeof process !== "undefined" ? process.cwd?.() : null,
    pluginRoot,
  ].filter(Boolean)

  for (const candidate of candidates) {
    let current = resolve(candidate)
    while (true) {
      if (existsSync(resolve(current, DIR_WORKFLOW))) {
        return current
      }
      const parent = resolve(current, "..")
      if (parent === current) {
        break
      }
      current = parent
    }
  }
  return pluginRoot
}

function pythonCandidates() {
  const list = []
  const env = (process.env.COWORK_FLOW_PYTHON || "").trim()
  if (env) list.push([env])
  list.push(["python3"], ["python"])
  if (process.platform === "win32") list.push(["py", "-3"])
  return list
}

// The project's own runtime copy wins (same root the CLI resolves);
// the payload's cached copy (cowork-flow/runtime/scripts) renders only
// outside any cowork-flow project, for the not-initialized context.
function resolveInjectScript(root) {
  if (root) {
    const projectInject = resolve(
      root,
      DIR_WORKFLOW,
      "scripts",
      "adapters",
      "host",
      "inject.py"
    )
    if (existsSync(projectInject)) return projectInject
  }
  const cacheInject = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "runtime",
    "scripts",
    "adapters",
    "host",
    "inject.py"
  )
  return existsSync(cacheInject) ? cacheInject : null
}

// One spawn attempt: stdin carries the synthesized hook payload,
// stdout is the injection text. A non-zero exit or a timeout skips
// the injection — the shim decorates the event, it must never break
// it — but the child's stderr and the skip reason still reach the
// host log (zcode shim parity), so a broken render stays debuggable.
function runInject(candidate, script, payload) {
  return new Promise((resolvePromise) => {
    let child
    try {
      child = spawn(candidate[0], [...candidate.slice(1), script, "--host", "opencode"], {
        stdio: ["pipe", "pipe", "pipe"],
        windowsHide: true,
      })
    } catch {
      resolvePromise({ ran: false, stdout: "" })
      return
    }
    let stdout = ""
    let stderr = ""
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      try {
        child.kill()
      } catch {
        // the transform must not be held up by a stuck render
      }
    }, INJECT_TIMEOUT_MS)
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk)
    })
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk)
    })
    child.on("error", () => {
      clearTimeout(timer)
      resolvePromise({ ran: false, stdout: "" })
    })
    child.on("close", (code) => {
      clearTimeout(timer)
      if (!child.pid) {
        // The interpreter never started (a missing binary can surface as a
        // close code instead of an error event): stay silent and let the
        // next candidate try.
        resolvePromise({ ran: false, stdout: "" })
        return
      }
      if (stderr.trim()) console.error(stderr.trimEnd())
      if (timedOut) {
        console.error(
          "cowork-flow opencode plugin: inject.py timed out; skipping injection"
        )
        resolvePromise({ ran: true, stdout: "" })
        return
      }
      if (code) {
        console.error(
          `cowork-flow opencode plugin: inject.py exited ${code}; skipping injection`
        )
      }
      resolvePromise({ ran: true, stdout })
    })
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(payload), "utf8")
  })
}

// The transform hook's single render path: forward the event to
// inject.py and hand back whatever it printed. The payload spreads the
// host input so every session/runtime-context key the Python identity
// table knows arrives unchanged; hook_event_name and cwd are the two
// fields the hook contract requires. `overrides` swaps the event name
// and adds the tool fields the PostToolUse contract needs.
async function renderViaInject(input, overrides = null) {
  if (
    process.env.COWORK_FLOW_HOOKS === "0" ||
    process.env.COWORK_FLOW_DISABLE_HOOKS === "1"
  ) {
    return ""
  }
  const root = findRepoRoot(input)
  const script = resolveInjectScript(root === pluginRoot ? null : root)
  if (!script) {
    return ""
  }
  const extra = overrides && typeof overrides === "object" ? overrides : {}
  const payload = {
    ...(input && typeof input === "object" ? input : {}),
    ...extra,
    hook_event_name: extra.hook_event_name || "UserPromptSubmit",
    cwd: inputCwd(input) || (root === pluginRoot ? null : root) || process.cwd(),
  }
  for (const candidate of pythonCandidates()) {
    if (!interpreterIsUsable(candidate)) {
      continue
    }
    const result = await runInject(candidate, script, payload)
    if (!result.ran) {
      continue
    }
    return result.stdout.trim()
  }
  console.error(
    "cowork-flow opencode plugin: no Python 3.10+ interpreter found; skipping injection"
  )
  return ""
}

// Editor-phase scope warning: opencode sessions get the same
// single-line out-of-scope advisory the other hosts receive on
// PostToolUse. Best-effort — a missing runtime, a timeout, or any
// error stays silent and never blocks the edit that already happened.
const EDIT_TOOL_NAMES = new Set(["edit", "write"])

function editedFilePath(input) {
  const tool = typeof input?.tool === "string" ? input.tool : ""
  if (!EDIT_TOOL_NAMES.has(tool)) {
    return ""
  }
  const args = input?.args
  const candidate = args && typeof args === "object" ? args.filePath : null
  return typeof candidate === "string" && candidate.trim() ? candidate.trim() : ""
}

async function renderEditScopeWarning(input) {
  const filePath = editedFilePath(input)
  if (!filePath) {
    return ""
  }
  return renderViaInject(input, {
    hook_event_name: "PostToolUse",
    tool_name: typeof input?.tool === "string" ? input.tool : "edit",
    tool_input: { file_path: filePath },
  })
}

function sanitize(value) {
  return String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "_")
    .replace(/^[._-]+|[._-]+$/g, "")
    .slice(0, 160)
}

function firstString(input, keys) {
  for (const key of keys) {
    const value = input?.[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }
  return null
}

function resolveOpenCodeSessionId(input) {
  const direct = firstString(input, [
    "OPENCODE_SESSION_ID",
    "opencode_session_id",
    "sessionID",
    "sessionId",
    "session_id",
  ])
  if (direct) {
    return sanitize(direct)
  }
  const nested = firstString(input?.session, ["id", "sessionID", "sessionId", "session_id"])
  return nested ? sanitize(nested) : null
}

function resolveContextKey(input) {
  const explicit = firstString(input, ["COWORK_FLOW_CONTEXT_ID", "cowork_flow_context_id", "context_id"])
  if (explicit) {
    return sanitize(explicit)
  }
  const opencodeSession = resolveOpenCodeSessionId(input)
  return opencodeSession ? `opencode_${sanitize(opencodeSession)}` : null
}

function injectShellEnv(input, output) {
  const contextKey = resolveContextKey(input)
  if (!contextKey) {
    return
  }
  if (!output.env || typeof output.env !== "object") {
    output.env = {}
  }
  if (!output.env.COWORK_FLOW_CONTEXT_ID) {
    output.env.COWORK_FLOW_CONTEXT_ID = contextKey
  }
  const opencodeSession = resolveOpenCodeSessionId(input)
  if (opencodeSession && !output.env.OPENCODE_SESSION_ID) {
    output.env.OPENCODE_SESSION_ID = opencodeSession
  }
}

// The payload's own skills directory, located from this
// module's file path and not from the repository root: the
// machine install puts this file in
// ~/.config/opencode/cowork-flow/ and the project install
// in <project>/.opencode/cowork-flow/, so a sibling
// skills/ resolves in both.
export function payloadSkillsDir() {
  return resolve(dirname(fileURLToPath(import.meta.url)), "skills")
}

// Register the payload skills directory so opencode
// discovers the bootstrap Skill in a repository that has
// no cowork-flow runtime — the reason the machine-level
// install exists at all. `config` is the cached object the
// host hands every plugin's `config` hook, so this
// mutation is visible to the skill scan that runs after it
// (opencode 1.1.53: Plugin.init runs before Skill.state,
// and Config.get returns the same cached state).
export function registerPayloadSkills(config) {
  if (!config || typeof config !== "object") {
    return
  }
  const dir = payloadSkillsDir()
  // A project install ships no skills/ sibling. opencode
  // skips a registered path that does not exist, so the
  // shared code needs no second variant.
  if (!existsSync(dir)) {
    return
  }
  // Read what is usable and write back a shape the host
  // can consume, without throwing on a config the schema
  // would reject anyway — a plugin must never be the
  // reason the host fails to start.
  const skills = config.skills && typeof config.skills === "object" ? config.skills : {}
  const paths = Array.isArray(skills.paths) ? skills.paths : []
  if (!paths.includes(dir)) {
    paths.push(dir)
  }
  skills.paths = paths
  config.skills = skills
}

// The plugin adapter imports the hook helpers; these are
// the unit-test surface (transport, fail-open, shell env,
// edit-scope delegation). opencode never reads this module.
export {
  renderViaInject,
  editedFilePath,
  renderEditScopeWarning,
  findRepoRoot,
  injectShellEnv,
}
