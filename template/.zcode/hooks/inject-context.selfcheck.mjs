#!/usr/bin/env node
/**
 * Self-check for inject-context.js
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync, rmSync, copyFileSync } from "fs";
import { join, dirname } from "path";
import { execSync } from "child_process";
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
  return execSync(`node ${hookScript}`, {
    env: { ...process.env, ...env },
    encoding: "utf8",
    cwd: import.meta.dirname,
    input: stdin,
  });
}

function copyScaffoldTemplate(repoRoot) {
  const src = join(import.meta.dirname, "..", "scaffold", ".cowork-flow", "spec", "contracts", "workflow-state-templates.md");
  const dest = join(repoRoot, ".cowork-flow", "spec", "contracts", "workflow-state-templates.md");
  if (existsSync(src)) {
    mkdirSync(dirname(dest), { recursive: true });
    copyFileSync(src, dest);
  }
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

  // Install templates.md so breadcrumb parsing can be tested
  copyScaffoldTemplate(tmpRoot);
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

  test("outputs contract-digest with fingerprint", () => {
    const result = runHook({ ZCODE_PROJECT_DIR: tmpRoot });
    const parsed = JSON.parse(result);
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /<contract-digest fingerprint="[a-f0-9]+">/, "should have contract-digest with hex fingerprint");
    assert.match(ctx, /<cowork-runtime host="zcode"/, "should have cowork-runtime block");
    assert.match(ctx, /RUNTIME_CONTEXT_DISPATCH_V2/, "should list contracts from registry");
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

} finally {
  cleanup();
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
