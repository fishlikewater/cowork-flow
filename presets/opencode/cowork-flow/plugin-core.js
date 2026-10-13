// Transport shim behind the opencode plugin. Every workflow fact
// (contract digest, workflow-state, decision anchor, stage contract,
// runtime-context bind) is rendered by the Python source
// <scripts>/adapters/host/inject.py --host opencode; this module moves
// bytes only. What stays here is what the Python side cannot reach:
// the config-hook skills registration, the shell.env context-key
// export, and the edit-phase spec-check the tool.execute.after hook
// delegates to the project runtime.
//
// This module must NOT live under plugins/: opencode
// treats every file directly inside plugins/ as a plugin
// and calls every export of it as a plugin factory, so
// library code there kills the host during bootstrap. A
// namespaced sibling directory also keeps the payload tree
// self-similar between a project install and the machine
// install, so the adapter's relative import resolves in
// both.

import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const DIR_WORKFLOW = ".cowork-flow"
// One prompt assembly must not wait longer than a host hook event.
const INJECT_TIMEOUT_MS = 4800

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
// fields the hook contract requires.
async function renderViaInject(input) {
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
  const payload = {
    ...(input && typeof input === "object" ? input : {}),
    hook_event_name: "UserPromptSubmit",
    cwd: inputCwd(input) || (root === pluginRoot ? null : root) || process.cwd(),
  }
  for (const candidate of pythonCandidates()) {
    const result = await runInject(candidate, script, payload)
    if (!result.ran) {
      continue
    }
    return result.stdout.trim()
  }
  return ""
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

// Editor-phase spec-check: opencode sessions get the same
// single-line violation hint zcode and claude-code
// receive. Best-effort — a missing runtime, a timeout, or
// any error stays silent and never blocks the edit that
// already happened.
const EDIT_TOOL_NAMES = new Set(["edit", "write"])
const EDIT_CHECK_TIMEOUT_MS = 2500

function editedFilePath(input) {
  const tool = typeof input?.tool === "string" ? input.tool : ""
  if (!EDIT_TOOL_NAMES.has(tool)) {
    return ""
  }
  const args = input?.args
  const candidate = args && typeof args === "object" ? args.filePath : null
  return typeof candidate === "string" && candidate.trim() ? candidate.trim() : ""
}

function runEditSpecCheck(root, filePath) {
  return new Promise((resolvePromise) => {
    let settled = false
    const finish = (value) => {
      if (!settled) {
        settled = true
        resolvePromise(value)
      }
    }
    const entry = resolve(
      root,
      DIR_WORKFLOW,
      process.platform === "win32" ? "run.cmd" : "run"
    )
    if (!existsSync(entry)) {
      finish("")
      return
    }
    let child
    try {
      child = spawn(
        entry,
        ["spec-check", "--phase", "edit", "--file", filePath, "--throttled"],
        {
          cwd: root,
          stdio: ["ignore", "pipe", "ignore"],
          shell: process.platform === "win32",
        }
      )
    } catch {
      finish("")
      return
    }
    const timer = setTimeout(() => {
      try {
        child.kill()
      } catch {
        // the edit must not be held up by a stuck checker
      }
      finish("")
    }, EDIT_CHECK_TIMEOUT_MS)
    let stdout = ""
    if (child.stdout) {
      child.stdout.on("data", (chunk) => {
        stdout += String(chunk)
      })
    }
    child.on("error", () => {
      clearTimeout(timer)
      finish("")
    })
    child.on("close", () => {
      clearTimeout(timer)
      finish(stdout.trim())
    })
  })
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
// edit-phase delegation). opencode never reads this module.
export {
  renderViaInject,
  editedFilePath,
  findRepoRoot,
  injectShellEnv,
  runEditSpecCheck,
}
