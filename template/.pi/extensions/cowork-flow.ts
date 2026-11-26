/**
 * cowork-flow workflow-state injection for Pi.
 *
 * Installed by `cwf host add pi` at `$PI_CODING_AGENT_DIR/extensions/cowork-flow.ts`
 * (default `~/.pi/agent/extensions/`) and owned by marker `CoworkFlowPiExtension`.
 *
 * The rendering stays in the project's Python entry
 * (`.cowork-flow/scripts/adapters/host/inject.py --host pi`); this file only
 * transports the rendered `additionalContext` into Pi. The state is injected
 * on `before_agent_start`, and only when the rendered text changed since the
 * last injection, so an unchanged task does not grow the transcript.
 *
 * Written as plain JavaScript with JSDoc types: Pi loads `.ts` directly, and
 * the test suite imports this file through a `.mjs` copy so the transport
 * behavior is executed, not just string-matched.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export const COWORK_FLOW_PI_MARKER = "CoworkFlowPiExtension";
const CUSTOM_TYPE = "cowork-flow";
const INJECT_RELATIVE = join(".cowork-flow", "scripts", "adapters", "host", "inject.py");

// Mirrors NOT_INITIALIZED_BODY in .cowork-flow/scripts/adapters/host/inject.py.
// The extension is machine-level, so a directory without a workflow root has
// no project inject.py to call; this fixed body is the only text it can
// transport there. A Python test pins both copies byte-for-byte.
const NOT_INITIALIZED_BODY = `<workflow-state>
Status: not_initialized
Source: cowork-flow-plugin
⚠️ 项目未初始化 cowork-flow 工作流。

请通过显式 init/sync 安装 cowork-flow 模板后再继续；hook 不会在注入阶段创建或复制项目文件。
</workflow-state>`;

/**
 * @param {string} start
 * @returns {string | null}
 */
function findWorkflowRoot(start) {
  let current = resolve(start);
  for (;;) {
    if (existsSync(join(current, ".cowork-flow"))) return current;
    const parent = dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

/** @returns {string} */
function pythonCommand() {
  const explicit = (process.env.COWORK_FLOW_PYTHON || "").trim();
  if (explicit) return explicit;
  return process.platform === "win32" ? "python" : "python3";
}

/**
 * @param {any} ctx
 * @returns {string}
 */
function sessionId(ctx) {
  try {
    return String(ctx.sessionManager.getSessionId() || "");
  } catch {
    return "";
  }
}

// Pi's shell tools export PI_SESSION_ID themselves; environments that do not
// (an embedded host, or a tool that spawns without session metadata) read it
// from here instead, so the CLI resolves the same `pi_<id>` context key.
/**
 * @param {string} id
 * @returns {void}
 */
function publishSessionId(id) {
  if (id && !(process.env.PI_SESSION_ID || "").trim()) {
    process.env.PI_SESSION_ID = id;
  }
}

/**
 * @param {string} root
 * @param {Record<string, unknown>} payload
 * @returns {Promise<{code: number, stdout: string}>}
 */
function runInject(root, payload) {
  const script = join(root, INJECT_RELATIVE);
  if (!existsSync(script)) return Promise.resolve({ code: -1, stdout: "" });
  return new Promise((done) => {
    const child = spawn(pythonCommand(), [script, "--host", "pi"], {
      cwd: root,
      windowsHide: true,
      env: { ...process.env, COWORK_FLOW_HOST: "pi" },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += String(chunk)));
    child.stderr.on("data", (chunk) => (stderr += String(chunk)));
    child.on("error", () => done({ code: -1, stdout: "" }));
    child.on("close", (code) => {
      // Injection never blocks the run: a broken runtime stays silent rather
      // than turning every turn into an error surface.
      if (code !== 0 && stderr) {
        done({ code: code ?? -1, stdout: "" });
        return;
      }
      done({ code: code ?? -1, stdout });
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

/**
 * @param {string} stdout
 * @returns {string}
 */
function readContext(stdout) {
  const text = stdout.trim();
  if (!text) return "";
  try {
    const parsed = JSON.parse(text);
    const envelope = parsed && parsed.hookSpecificOutput && parsed.hookSpecificOutput.additionalContext;
    return typeof envelope === "string" ? envelope : "";
  } catch {
    return "";
  }
}

/**
 * @param {any} pi
 * @returns {void}
 */
export default function (pi) {
  let lastInjected = "";
  let started = false;

  pi.on("before_agent_start", async (event, ctx) => {
    if (event.messageType === "custom") return;
    const root = findWorkflowRoot(ctx.cwd);
    if (!root) {
      if (lastInjected === NOT_INITIALIZED_BODY) return;
      lastInjected = NOT_INITIALIZED_BODY;
      return {
        message: {
          customType: CUSTOM_TYPE,
          content: NOT_INITIALIZED_BODY,
          display: false,
        },
      };
    }
    const id = sessionId(ctx);
    publishSessionId(id);
    const result = await runInject(root, {
      hook_event_name: started ? "UserPromptSubmit" : "SessionStart",
      cwd: root,
      PI_SESSION_ID: id,
    });
    if (result.code !== 0) return;
    started = true;
    const context = readContext(result.stdout);
    if (!context || context === lastInjected) return;
    lastInjected = context;
    return {
      message: {
        customType: CUSTOM_TYPE,
        content: context,
        display: false,
      },
    };
  });
}
