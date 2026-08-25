#!/usr/bin/env node
/**
 * Self-check for inject-context.js
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync, rmSync } from "fs";
import { join, dirname } from "path";
import { spawnSync } from "child_process";
import assert from "assert/strict";

const tmpRoot = join(import.meta.dirname, ".selfcheck-tmp");
const hookScript = join(import.meta.dirname, "inject-context.js");

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${err.message}`);
    failed++;
  }
}

function runHook(env = {}, stdin) {
  const result = spawnSync(process.execPath, [hookScript], {
    env: { ...process.env, ...env },
    encoding: "utf8",
    cwd: import.meta.dirname,
    input: stdin,
  });
  if (result.status !== 0) {
    const error = new Error(result.stderr || `hook exited with ${result.status}`);
    error.status = result.status;
    throw error;
  }
  return result.stdout;
}

function writeProjectFile(repoRoot, relativePath, content) {
  const dest = join(repoRoot, relativePath);
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, content, "utf8");
}

function writeMinimalWorkflowSpec(repoRoot) {
  writeProjectFile(repoRoot, "AGENTS.md", "# Test Project\n");
  writeProjectFile(repoRoot, ".cowork-flow/config.yaml", "codex:\n  dispatch_mode: inline\n");
  writeProjectFile(repoRoot, ".cowork-flow/run", "#!/usr/bin/env sh\n");
  writeProjectFile(
    repoRoot,
    ".cowork-flow/spec/runtime/contract-registry.json",
    JSON.stringify({
      schemaVersion: 1,
      contracts: [
        {
          id: "RUNTIME_CONTEXT_DISPATCH_V2",
          path: ".cowork-flow/spec/contracts/subagent-dispatch.md",
          digest: [
            "Formal subagent work is keyed by cowork_runtime_context_id.",
            "Explicit shim bind records bound_context_key before formal output is accepted.",
          ],
          readWhen: ["before formal subagent dispatch"],
        },
      ],
    }, null, 2) + "\n"
  );
  writeProjectFile(
    repoRoot,
    ".cowork-flow/spec/contracts/subagent-dispatch.md",
    "# Subagent Dispatch\n\nFormal subagent work is keyed by cowork_runtime_context_id.\n"
  );
  writeProjectFile(
    repoRoot,
    ".cowork-flow/spec/contracts/workflow-state-templates.md",
    [
      "[workflow-state:no_task]",
      "STOP - no active task. Use task next --run to create or start a task.",
      "[/workflow-state:no_task]",
      "",
      "[workflow-state:in_progress]",
      "活动任务正在执行。",
      "[/workflow-state:in_progress]",
    ].join("\n")
  );
}

function setupFakeProject() {
  const coworkDir = join(tmpRoot, ".cowork-flow");
  const sessionsDir = join(coworkDir, ".runtime", "sessions");
  const taskDir = join(coworkDir, "tasks", "07-02-test-task");
  mkdirSync(sessionsDir, { recursive: true });
  mkdirSync(taskDir, { recursive: true });

  const sessData = JSON.stringify({ active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" });
  writeFileSync(join(sessionsDir, "claude_abc.json"), sessData, "utf8");
  const taskData = JSON.stringify({ title: "Test Task", status: "in_progress" });
  writeFileSync(join(taskDir, "task.json"), taskData, "utf8");

  // Install minimal project specs so breadcrumb parsing can be tested without plugin scaffold.
  writeMinimalWorkflowSpec(tmpRoot);
}

function cleanup() {
  rmSync(tmpRoot, { recursive: true, force: true });
}

console.log("inject-context self-check\n");

try {
  setupFakeProject();

  test("outputs valid JSON to stdout via env var", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    assert.ok(parsed.hookSpecificOutput, "should have hookSpecificOutput");
    assert.ok(parsed.hookSpecificOutput.additionalContext, "should have additionalContext");
    assert.equal(parsed.hookSpecificOutput.hookEventName, "UserPromptSubmit");
  });

  test("reads active task and outputs correct Task/Status", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Task: \.cowork-flow\/tasks\/07-02-test-task/);
    assert.match(ctx, /Status: in_progress/);
  });

  test("reports not_initialized without scaffolding when ZCODE_PROJECT_DIR has none", () => {
    const scaffoldTmp = join(import.meta.dirname, ".scaffold-test");
    if (existsSync(scaffoldTmp)) rmSync(scaffoldTmp, { recursive: true, force: true });
    const emptyDir = join(scaffoldTmp, "fresh-proj");
    mkdirSync(emptyDir, { recursive: true });
    const result = runHook({ ZCODE_PROJECT_DIR: emptyDir });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /not_initialized/);
    assert.match(ctx, /hook 不会在注入阶段创建或复制项目文件/);
    assert.ok(!existsSync(join(emptyDir, ".cowork-flow")), ".cowork-flow should not be created");
    assert.ok(!existsSync(join(emptyDir, "AGENTS.md")), "AGENTS.md should not be created");
  });

  test("workflow-state block is well-formed XML", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /<workflow-state>/);
    assert.match(ctx, /<\/workflow-state>/);
  });

  test("additionalContext is non-empty string", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    assert.equal(typeof parsed.hookSpecificOutput.additionalContext, "string");
    assert.ok(parsed.hookSpecificOutput.additionalContext.length > 50);
  });

  test("exit code is 0 on success", () => {
    try {
      runHook({ ZCODE_PROJECT_DIR: tmpRoot });
      assert.ok(true);
    } catch (err) {
      assert.fail(`Hook exited with code ${err.status}`);
    }
  });

  test("cursor platform outputs additional_context (no hookSpecificOutput)", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot, CURSOR_PLUGIN_ROOT: "/x" });
    const parsed = JSON.parse(result);
    assert.ok(parsed.additional_context, "cursor format uses additional_context");
    assert.ok(!parsed.hookSpecificOutput, "cursor format should not have hookSpecificOutput");
  });

  test("UserPromptSubmit outputs a single fingerprint line without contract details", () => {
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ hook_event_name: "UserPromptSubmit" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /<contract-fingerprint value="[a-f0-9]+"\/>/, "should carry the repeated fingerprint");
    assert.doesNotMatch(ctx, /<contract-digest/, "digest block must not appear on user prompts");
    assert.doesNotMatch(ctx, /RUNTIME_CONTEXT_DISPATCH_V2/, "contract detail lines must not appear");
  });

  test("SessionStart outputs the full contract-digest block", () => {
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ hook_event_name: "SessionStart" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /<cowork-runtime host="zcode"/, "should have cowork-runtime block");
    assert.match(ctx, /<contract-digest fingerprint="[a-f0-9]+">/, "should have contract-digest with hex fingerprint");
    assert.match(ctx, /RUNTIME_CONTEXT_DISPATCH_V2/, "should list contracts from registry");
  });

  test("fingerprint is stable across events and reacts to spec changes", () => {
    const promptFingerprint = () => {
      const parsed = JSON.parse(
        runHook({ ZCODE_PROJECT_DIR: tmpRoot }, JSON.stringify({ hook_event_name: "UserPromptSubmit" }))
      );
      return parsed.hookSpecificOutput.additionalContext.match(/<contract-fingerprint value="([a-f0-9]+)"\/>/)[1];
    };
    const before = promptFingerprint();
    const sessionParsed = JSON.parse(
      runHook({ ZCODE_PROJECT_DIR: tmpRoot }, JSON.stringify({ hook_event_name: "SessionStart" }))
    );
    const sessionFingerprint = sessionParsed.hookSpecificOutput.additionalContext.match(/fingerprint="([a-f0-9]+)"/)[1];
    assert.equal(before, sessionFingerprint, "identical spec state must yield identical fingerprints");

    const specPath = join(tmpRoot, ".cowork-flow", "spec", "contracts", "subagent-dispatch.md");
    writeFileSync(specPath, "# Subagent Dispatch\n\nChanged content moves the fingerprint.\n", "utf8");
    const after = promptFingerprint();
    assert.notEqual(before, after, "spec content changes must move the fingerprint");
  });

  test("parses workflow-state-templates.md for breadcrumb text", () => {
    // Remove session files to simulate no active task
    const sessionsDir = join(tmpRoot, ".cowork-flow", ".runtime", "sessions");
    if (existsSync(sessionsDir)) {
      rmSync(sessionsDir, { recursive: true, force: true });
    }
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    const m = ctx.match(/<workflow-state>([\s\S]*?)<\/workflow-state>/);
    assert.ok(m, "should have workflow-state block");
    assert.match(m[1], /STOP/, "no_task breadcrumb should contain STOP marker from templates.md");
  });

  test("outputs in_progress breadcrumb when task is active", () => {
    const sessionsDir = join(tmpRoot, ".cowork-flow", ".runtime", "sessions");
    const taskDir = join(tmpRoot, ".cowork-flow", "tasks", "test-active");
    mkdirSync(sessionsDir, { recursive: true });
    mkdirSync(taskDir, { recursive: true });
    const sessData = JSON.stringify({ active_task_path: ".cowork-flow/tasks/test-active", scope: "main", platform: "zcode", last_seen_at: "2026-07-02T16:00:00Z" });
    writeFileSync(join(sessionsDir, "test_sess.json"), sessData, "utf8");
    const taskData = JSON.stringify({ status: "in_progress" });
    writeFileSync(join(taskDir, "task.json"), taskData, "utf8");
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Status: in_progress/, "should show in_progress status");
    assert.match(ctx, /活动任务正在执行/, "should contain in_progress breadcrumb from templates.md");
  });

  test("detects delegated_subtask from prompt context ID", () => {
    const subagentsDir = join(tmpRoot, ".cowork-flow", ".runtime", "subagents");
    mkdirSync(subagentsDir, { recursive: true });
    const contextId = "rtx_test_001";
    const taskId = ".cowork-flow/tasks/test-active";
    const contextData = JSON.stringify({ scope: "subagent", agent_type: "cowork-implement", task_dir: taskId, status: "bound", assignment: { goal: "Implement feature X" } });
    writeFileSync(join(subagentsDir, `${contextId}.json`), contextData, "utf8");
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot, COWORK_FLOW_RUNTIME_CONTEXT_ID: contextId });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Status: delegated_subtask/, "should detect delegated_subtask");
    assert.match(ctx, /Scope: subagent/, "should show subagent scope");
  });

  // --- Stale-session poisoning regression (per-session selection) ---

  function resetSessions(entries) {
    const sessionsDir = join(tmpRoot, ".cowork-flow", ".runtime", "sessions");
    rmSync(sessionsDir, { recursive: true, force: true });
    mkdirSync(sessionsDir, { recursive: true });
    for (const [name, data] of Object.entries(entries)) {
      writeFileSync(
        join(sessionsDir, name),
        JSON.stringify(data),
        "utf8"
      );
    }
  }

  function ensureTask(taskName, status = "in_progress") {
    const taskDir = join(tmpRoot, ".cowork-flow", "tasks", taskName);
    mkdirSync(taskDir, { recursive: true });
    writeFileSync(join(taskDir, "task.json"), JSON.stringify({ status }), "utf8");
  }

  test("prefers the session file matching hook input sessionId over a newer global entry", () => {
    ensureTask("07-02-test-task");
    ensureTask("07-03-newer-task");
    resetSessions({
      "zcode_my-session.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "zcode", last_seen_at: "2026-07-02T13:00:00Z" },
      "claude_other.json": { active_task_path: ".cowork-flow/tasks/07-03-newer-task", scope: "main", platform: "claude", last_seen_at: "2026-07-03T18:00:00Z" },
    });
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ session_id: "my-session" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Task: \.cowork-flow\/tasks\/07-02-test-task/, "own session binding wins over newer global entry");
  });

  test("skips stale sessions whose task directory is gone and falls back to the newest valid one", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "zcode_gone.json": { active_task_path: ".cowork-flow/tasks/06-21-deleted-task", scope: "main", platform: "zcode", last_seen_at: "2026-08-01T09:00:00Z" },
      "claude_abc.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" },
    });
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Task: \.cowork-flow\/tasks\/07-02-test-task/, "newest valid session wins after skipping stale");
    assert.doesNotMatch(ctx, /任务目录不存在/, "stale path must not leak into injected state");
  });

  test("reports clean no_task when every session points to a missing task", () => {
    resetSessions({
      "zcode_gone.json": { active_task_path: ".cowork-flow/tasks/06-21-deleted-task", scope: "main", platform: "zcode", last_seen_at: "2026-08-01T09:00:00Z" },
    });
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    const m = ctx.match(/<workflow-state>([\s\S]*?)<\/workflow-state>/);
    assert.ok(m, "should have workflow-state block");
    assert.match(m[1], /Status: no_task/, "should fall back to clean no_task");
    assert.doesNotMatch(m[1], /06-21-deleted-task/, "must not reference the dead task path");
  });

  test("main-session fallback ignores subagent-scoped session files", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "subagent_child.json": { active_task_path: ".cowork-flow/tasks/sub-child", scope: "subagent", platform: "zcode", last_seen_at: "2026-08-05T09:00:00Z" },
      "claude_abc.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" },
    });
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Task: \.cowork-flow\/tasks\/07-02-test-task/, "main-scope session is selected, not the newer subagent one");
  });

  test("explicit sessionId without own session file reports no_task with rebind hints", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "claude_other.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-03T18:00:00Z" },
    });
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ hook_event_name: "UserPromptSubmit", session_id: "brand-new" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    const m = ctx.match(/<workflow-state>([\s\S]*?)<\/workflow-state>/);
    assert.ok(m, "should have workflow-state block");
    assert.match(m[1], /Status: no_task/, "unbound explicit session must be no_task");
    assert.doesNotMatch(m[1], /Task: \./, "must not adopt another session's task");
    assert.match(m[1], /07-02-test-task/, "should list active tasks for rebinding");
  });

  test("dead-path session shows rebind hints for remaining active tasks", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "zcode_stale.json": { active_task_path: ".cowork-flow/tasks/06-21-deleted", scope: "main", platform: "zcode", last_seen_at: "2026-08-01T09:00:00Z" },
    });
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ hook_event_name: "UserPromptSubmit", session_id: "stale" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    const m = ctx.match(/<workflow-state>([\s\S]*?)<\/workflow-state>/);
    assert.ok(m, "should have workflow-state block");
    assert.match(m[1], /06-21-deleted/, "own stale binding is reported as-is");
    assert.match(m[1], /07-02-test-task/, "remaining active task offered for rebinding");
  });

  test("unbound session with zero active tasks stays clean without hints", () => {
    rmSync(join(tmpRoot, ".cowork-flow", "tasks"), { recursive: true, force: true });
    resetSessions({});
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({ hook_event_name: "UserPromptSubmit", session_id: "fresh" })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    const m = ctx.match(/<workflow-state>([\s\S]*?)<\/workflow-state>/);
    assert.ok(m, "should have workflow-state block");
    assert.match(m[1], /Status: no_task/);
    assert.doesNotMatch(m[1], /改绑|rebind/i, "no hints when nothing to rebind to");
  });

  test("PostToolUse refreshes state when the command runs task lifecycle", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "claude_abc.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" },
    });
    const result = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({
        hook_event_name: "PostToolUse",
        tool_input: { command: "./.cowork-flow/run task next --run --title X" },
      })
    );
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.equal(parsed.hookSpecificOutput.hookEventName, "PostToolUse");
    assert.match(ctx, /Status: in_progress/, "mid-turn refresh carries updated state");
    assert.match(ctx, /<contract-fingerprint value="[a-f0-9]+"\/>/, "fingerprint line rides the refresh");
    assert.doesNotMatch(ctx, /<contract-digest/, "no full digest outside session start");
  });

  test("PostToolUse stays silent for unrelated commands", () => {
    resetSessions({});
    const stdout = runHook(
      { ZCODE_PROJECT_DIR: tmpRoot },
      JSON.stringify({
        hook_event_name: "PostToolUse",
        tool_input: { command: "ls -la" },
      })
    );
    assert.equal(stdout.trim(), "", "unrelated commands must produce no output");
  });

  test("consistent state snapshot drives breadcrumb key selection", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "claude_abc.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" },
    });
    const templatesPath = join(tmpRoot, ".cowork-flow", "spec", "contracts", "workflow-state-templates.md");
    const templates = readFileSync(templatesPath, "utf8");
    writeFileSync(
      templatesPath,
      `${templates}\n[workflow-state:snapshot-probe]\n快照键生效。\n[/workflow-state:snapshot-probe]\n`,
      "utf8"
    );
    const runtimeDir = join(tmpRoot, ".cowork-flow", ".runtime");
    mkdirSync(runtimeDir, { recursive: true });
    writeFileSync(
      join(runtimeDir, "state-snapshot.json"),
      JSON.stringify({
        schemaVersion: 1,
        generatedAt: "2026-07-02T13:05:00Z",
        activeTaskPath: ".cowork-flow/tasks/07-02-test-task",
        status: "in_progress",
        breadcrumbKey: "snapshot-probe",
      }),
      "utf8"
    );
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /Task: \.cowork-flow\/tasks\/07-02-test-task/);
    assert.match(ctx, /快照键生效。/, "consistent snapshot key wins over status convention");
    assert.doesNotMatch(ctx, /活动任务正在执行/, "status-derived fallback must not run");
  });

  test("mismatched or missing snapshot falls back to status-derived breadcrumb", () => {
    ensureTask("07-02-test-task");
    resetSessions({
      "claude_abc.json": { active_task_path: ".cowork-flow/tasks/07-02-test-task", scope: "main", platform: "claude", last_seen_at: "2026-07-02T13:00:00Z" },
    });
    const runtimeDir = join(tmpRoot, ".cowork-flow", ".runtime");
    mkdirSync(runtimeDir, { recursive: true });
    const snapshotPath = join(runtimeDir, "state-snapshot.json");
    writeFileSync(
      snapshotPath,
      JSON.stringify({
        schemaVersion: 1,
        generatedAt: "2026-07-02T13:05:00Z",
        activeTaskPath: ".cowork-flow/tasks/some-other-task",
        status: "review",
        breadcrumbKey: "review",
      })
    );
    const parsedFor = () => {
      const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
      return JSON.parse(result).hookSpecificOutput.additionalContext;
    };
    assert.match(parsedFor(), /活动任务正在执行/, "foreign snapshot must be ignored");
    rmSync(snapshotPath);
    assert.match(parsedFor(), /活动任务正在执行/, "missing snapshot falls back cleanly");
  });

} finally {
  cleanup();
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
