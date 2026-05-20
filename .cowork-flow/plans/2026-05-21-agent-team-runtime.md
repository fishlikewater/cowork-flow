# Agent Team Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在执行 plan 阶段提供一个平台中立、默认面向 Codex 的 agent team runtime，让主 agent 能把可独立任务拆分为可并行分派的 assignments，并把执行、审阅、重试和恢复状态结构化落盘。

**Architecture:** 采用“主 agent 调度型”模型：Python 脚本负责生成调度图、分派工件和状态记录，主 agent 负责审核、调度、协调和集成。默认适配器为 `codex`，`manual` 作为兜底；registry、policy 和 task 级工件全部放在 `.cowork-flow/` 下，保证可恢复、可测试、可同步。

**Tech Stack:** Node.js 仅负责现有 CLI/模板测试；核心实现使用 Python 3 标准库；计划解析、状态写入和简单 YAML 生成不引入第三方依赖。

**Current Execution Status:** Task 1 到 Task 6 已完成；全量验证、change/task 校验、session 记录和 current-task 清理均已完成。

---

### Task 1: 建立 agent-team 模板和同步边界

**Files:**
- Modify: `src/lib/copy-template.js`
- Modify: `test/sync.test.js`
- Modify: `tests/test_template_convergence.py`
- Modify: `tests/test_flow_script_paths.py`
- Modify: `README.md`
- Modify: `template/AGENTS.md`
- Add: `template/.cowork-flow/agent-team/agents.yaml`
- Add: `template/.cowork-flow/agent-team/adapters.yaml`
- Add: `template/.cowork-flow/agent-team/policy.yaml`
- Add: `template/.agent/skills/agent-team-execution/SKILL.md`

- [x] **Step 1: 先写失败测试，锁定模板与同步边界**

```javascript
test('sync preserves project-level agent-team configuration', async (t) => {
  const target = await createTempDir(t);
  await main(['init', target], { io: createIo() });
  await writeFile(join(target, '.cowork-flow', 'agent-team', 'agents.yaml'), 'custom: true\n', 'utf8');

  const code = await main(['sync', target], { io: createIo() });

  assert.equal(code, 0);
  assert.equal(await readText(join(target, '.cowork-flow', 'agent-team', 'agents.yaml')), 'custom: true\n');
});
```

```python
def test_template_ships_agent_team_assets(self) -> None:
    self.assertTrue((TEMPLATE / ".cowork-flow" / "agent-team" / "agents.yaml").is_file())
    self.assertTrue((TEMPLATE / ".agent" / "skills" / "agent-team-execution" / "SKILL.md").is_file())
```

- [x] **Step 2: 跑测试，确认当前仓库还不满足新规格**

Run:

```bash
npm test -- test/sync.test.js tests/test_template_convergence.py tests/test_flow_script_paths.py
```

Expected: fail on missing `agent-team` assets and sync protection.

- [x] **Step 3: 写最小实现**

```yaml
default_adapter: codex
fallback_adapter: manual
agents:
  implementer:
    codex_type: worker
    capabilities: [implementation]
```

把 `.cowork-flow/agent-team/` 加入同步保护前缀，并更新模板 README / AGENTS / skill 触发说明。

- [x] **Step 4: 再跑测试确认通过**

Run:

```bash
npm test -- test/sync.test.js tests/test_template_convergence.py tests/test_flow_script_paths.py
```

Expected: pass。

- [x] **Step 5: 记录本任务改动**

写明新增模板文件、同步保护规则和 skill 入口说明，便于后续 plan 执行者快速定位。

---

### Task 2: 实现 agent-team 命令骨架与项目级配置初始化

**Files:**
- Add: `template/.cowork-flow/scripts/agent_team.py`
- Add: `tests/test_agent_team_runtime.py`
- Modify: `template/.cowork-flow/scripts/common/paths.py`
- Modify: `template/.cowork-flow/scripts/common/git_context.py`
- Modify: `tests/test_python_runner.py`

- [x] **Step 1: 先写失败测试，锁定命令入口与 init 行为**

```python
def test_agent_team_init_creates_project_config(self) -> None:
    result = self.run_agent_team("init")

    self.assertEqual(0, result.returncode, result.stderr)
    self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "agents.yaml").is_file())
    self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "adapters.yaml").is_file())
    self.assertTrue((self.repo / ".cowork-flow" / "agent-team" / "policy.yaml").is_file())
```

```python
def test_runner_maps_agent_team_command(self) -> None:
    expected_script = ROOT / "template" / ".cowork-flow" / "scripts" / "agent_team.py"
    self.assertEqual(f"{python3} {expected_script} init", self.read_log(temp_dir)[-1])
```

- [x] **Step 2: 跑测试，确认还没有 agent-team 命令**

Run:

```bash
python -m unittest discover tests -v
```

Expected: fail because `agent_team.py` and associated tests are not implemented yet.

- [x] **Step 3: 写最小实现**

```python
def cmd_init(args: argparse.Namespace) -> int:
    repo_root = get_repo_root()
    agent_team_dir = repo_root / DIR_WORKFLOW / "agent-team"
    agent_team_dir.mkdir(parents=True, exist_ok=True)
    # 写入默认 agents.yaml / adapters.yaml / policy.yaml
    return 0
```

为 `run` 的自动脚本加载保留现有 fallback 机制，不改 `bin/cowork-flow.js`。

- [x] **Step 4: 再跑测试确认通过**

Run:

```bash
python -m unittest discover tests -v
```

Expected: `agent-team init` 创建默认配置，`run` 能映射 `agent_team.py`。

- [x] **Step 5: 记录命令骨架与目录约定**

写清楚命令组只依赖 `.cowork-flow/scripts/agent_team.py`，因此不需要改 `src/cli.js` 的命令路由。

---

### Task 3: 实现 plan 解析、依赖图和 dispatch-plan 生成

**Files:**
- Add: `template/.cowork-flow/scripts/common/agent_team.py`
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Add: `tests/test_agent_team_plan_parser.py`
- Add: `tests/fixtures/agent-team/sample-plan.md`

- [x] **Step 1: 先写失败测试，锁定标准 plan 解析规则**

```python
def test_prepare_parses_tasks_and_files(self) -> None:
    result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))

    self.assertEqual(0, result.returncode, result.stderr)
    dispatch = (self.task_dir / "agent-team" / "dispatch-plan.yaml").read_text(encoding="utf-8")
    self.assertIn("Task 1", dispatch)
    self.assertIn("implementer", dispatch)
    self.assertIn("spec-reviewer", dispatch)
```

```python
def test_prepare_rejects_empty_or_unparseable_plan(self) -> None:
    self.plan_file.write_text("# Broken\n", encoding="utf-8")
    result = self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))
    self.assertNotEqual(0, result.returncode)
    self.assertIn("unable to parse", result.stderr.lower())
```

- [x] **Step 2: 跑测试，确认当前没有解析器**

Run:

```bash
python -m unittest discover tests/test_agent_team_plan_parser.py -v
```

Expected: fail on missing parser and missing dispatch-plan output.

- [x] **Step 3: 写最小实现**

```python
def parse_plan(text: str) -> list[dict[str, object]]:
    # 识别 ### Task N: 标题、Files、checkbox、Run 命令和显式依赖
    tasks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = re.match(r"^### Task (\\d+):\\s*(.+)$", line)
        if match:
            current = {"number": int(match.group(1)), "title": match.group(2), "steps": [], "files": []}
            tasks.append(current)
        elif current is not None and line.strip().startswith("- [ ]"):
            current["steps"].append(line.strip())
    return tasks

def build_dispatch_plan(tasks: list[dict[str, object]], registry: dict[str, object]) -> dict[str, object]:
    # 基于文件重叠、显式依赖和阶段类型生成批次
    assignments = []
    for task in tasks:
        task_id = f"T{int(task['number']):03d}"
        assignments.append({"id": f"{task_id}-implementer", "task": task_id, "role": "implementer", "depends_on": []})
        assignments.append({"id": f"{task_id}-spec-reviewer", "task": task_id, "role": "spec-reviewer", "depends_on": [f"{task_id}-implementer"]})
        assignments.append({"id": f"{task_id}-quality-reviewer", "task": task_id, "role": "quality-reviewer", "depends_on": [f"{task_id}-spec-reviewer"]})
    return {"version": 1, "adapter": "codex", "assignments": assignments}
```

`dispatch-plan.yaml` 采用手写 YAML 输出，避免引入第三方解析器。

- [x] **Step 4: 再跑测试确认通过**

Run:

```bash
python -m unittest discover tests/test_agent_team_plan_parser.py -v
```

Expected: plan task、文件范围、依赖和风险标记都能正确落盘。

- [x] **Step 5: 写入结果文件结构约定**

确定 `dispatch-plan.yaml` 至少包含：

```yaml
version: 1
adapter: codex
tasks:
  - id: T001
    title: Add login guard
    files:
      - AGENTS.md
    depends_on: []
    recommended_agent: implementer
```

---

### Task 4: 实现状态机、next/status/record/retry/complete 与 metrics

**Files:**
- Modify: `template/.cowork-flow/scripts/agent_team.py`
- Add: `tests/test_agent_team_state_machine.py`
- Modify: `template/.cowork-flow/scripts/common/git_context.py`

- [x] **Step 1: 先写失败测试，锁定状态转移与历史保留**

```python
def test_record_result_appends_attempt_history(self) -> None:
    self.run_agent_team("prepare", str(self.task_dir), "--plan", str(self.plan_file))
    first = self.run_agent_team("record-result", str(self.task_dir), "--assignment", "T001-implementer", "--status", "done", "--file", str(self.result_file))

    self.assertEqual(0, first.returncode, first.stderr)
    status = json.loads((self.task_dir / "agent-team" / "status.json").read_text(encoding="utf-8"))
    self.assertEqual(1, status["assignments"]["T001-implementer"]["attempts"])
```

```python
def test_complete_fails_when_reviews_are_pending(self) -> None:
    result = self.run_agent_team("complete", str(self.task_dir))
    self.assertNotEqual(0, result.returncode)
    self.assertIn("pending", result.stderr.lower())
```

- [x] **Step 2: 跑测试，确认状态机行为缺失**

Run:

```bash
python -m unittest discover tests/test_agent_team_state_machine.py -v
```

Expected: fail until state files、retry 和 completion checks exist.

- [x] **Step 3: 写最小实现**

```python
def record_result(task_dir: Path, assignment_id: str, status: str, payload: dict[str, object]) -> None:
    # 追加 attempt，更新 assignment 状态和 metrics
    status_path = task_dir / "agent-team" / "status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    assignment = data["assignments"][assignment_id]
    assignment["attempts"] = int(assignment.get("attempts", 0)) + 1
    assignment["status"] = status
    status_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def complete(task_dir: Path) -> int:
    # 只有全部 done / approved / no-blocker 才能成功
    status_path = task_dir / "agent-team" / "status.json"
    data = json.loads(status_path.read_text(encoding="utf-8"))
    unfinished = [item_id for item_id, item in data["assignments"].items() if item.get("status") not in {"done", "approved"}]
    if unfinished:
        print("Error: pending assignments: " + ", ".join(unfinished), file=sys.stderr)
        return 1
    print("agent team complete")
    return 0
```

在 `git_context.py` 的最小恢复清单里补充 `agent-team status` / `agent-team next` 的定位提示，确保恢复时能看到调度层状态。

- [x] **Step 4: 再跑测试确认通过**

Run:

```bash
python -m unittest discover tests/test_agent_team_state_machine.py -v
```

Expected: `next` 只返回 ready assignments，`record-*` 不覆盖历史，`retry` 追加 attempt，`complete` 只在全通过时成功。

- [x] **Step 5: 同步 metrics 约定**

确认 `metrics.json` 至少包含：

```json
{
  "assignments": 3,
  "attempts": 5,
  "successfulAssignments": 2,
  "failedAssignments": 1,
  "reviewReworks": 1
}
```

---

### Task 5: 接入 workflow、start skill、README 与 template 说明

**Files:**
- Modify: `.cowork-flow/workflow.md`
- Modify: `.agent/skills/start/SKILL.md`
- Modify: `.agent/skills/executing-plans/SKILL.md`
- Modify: `README.md`
- Modify: `template/AGENTS.md`
- Modify: `tests/test_template_convergence.py`
- Add: `tests/test_agent_team_docs.py`

- [x] **Step 1: 先写失败测试，锁定文档触达点**

```python
def test_template_mentions_agent_team_runtime(self) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    self.assertIn("agent-team", readme)
    self.assertIn("codex", readme.lower())
```

```python
def test_workflow_mentions_agent_team_execution(self) -> None:
    workflow = (ROOT / ".cowork-flow" / "workflow.md").read_text(encoding="utf-8")
    self.assertIn("agent team", workflow.lower())
```

- [x] **Step 2: 跑测试，确认当前文档还没接入**

Run:

```bash
python -m unittest discover tests/test_agent_team_docs.py -v
```

Expected: fail until README / workflow / skills are updated.

- [x] **Step 3: 写最小实现**

在 workflow 的执行阶段增加明确说明：

```text
当 plan 存在可并行任务且环境支持 Codex 子 agent 时，可以使用 agent-team prepare / next / record-* / retry / complete。
```

在 `start` skill 中增加一段简短接入说明，指出主 agent 先恢复 task，再决定是否启用 agent team。

- [x] **Step 4: 再跑测试确认通过**

Run:

```bash
python -m unittest discover tests/test_agent_team_docs.py -v
```

Expected: 文档中都能看到 agent team 入口和默认 codex 适配器说明。

- [x] **Step 5: 清理措辞并保持与项目风格一致**

所有新增中文说明保持简洁，避免把 workflow 变成二次教程。

---

### Task 6: 最终验证、计划同步与收尾

**Files:**
- Modify: `.cowork-flow/changes/agent-team-runtime/change.yaml`
- Modify: `.cowork-flow/tasks/<task>/prd.md`
- Add: `.cowork-flow/tasks/<task>/implement.jsonl`
- Add: `.cowork-flow/tasks/<task>/check.jsonl`
- Add: `.cowork-flow/tasks/<task>/debug.jsonl`

- [x] **Step 1: 写 task PRD，把 change/spec/design/plan 汇总进任务上下文**

```markdown
## Goal
实现 agent-team runtime，让主 agent 能在 plan 执行阶段拆分、并行、审阅、重试和恢复。

## Requirements
- 默认 Codex 适配器
- 任务目录内 agent-team 工件
- plan 解析与依赖图
- 状态机与恢复
```

- [x] **Step 2: 初始化任务上下文并写入计划文件**

Run:

```bash
./.cowork-flow/run task init-context "$TASK_DIR" fullstack
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/agent-team-runtime/proposal.md" "Approved change proposal"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/agent-team-runtime/spec.md" "Approved behavior spec"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/changes/agent-team-runtime/design.md" "Approved design"
./.cowork-flow/run task add-context "$TASK_DIR" implement ".cowork-flow/plans/2026-05-21-agent-team-runtime.md" "Approved implementation plan"
```

- [x] **Step 3: 跑全量验证**

Run:

```bash
npm test
npm run test:template
npm run pack:check
```

Expected: Node tests、模板 Python tests、npm pack 检查全部通过。

- [x] **Step 4: 核对 change / plan / task 状态一致**

确认：

- `change.yaml` 已关联 plan 和 task。
- plan 的 checkbox 状态与真实进度一致。
- task 的 `implement.jsonl`、`check.jsonl`、`debug.jsonl` 已写入必要上下文。
- `agent-team` 状态可通过 `status` 和 `next` 恢复。

- [x] **Step 5: 收尾记录**

按项目策略补 session 记录，并在完成前再次跑 `./.cowork-flow/run resume` 做一次最小恢复检查。
