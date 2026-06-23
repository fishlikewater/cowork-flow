# TDD 产品化与门禁架构设计

## 目标

在不一次性重写全部 runtime 的前提下，建立可渐进落地的门禁架构，使 TDD、测试意图、编码规范和流程状态成为可执行产品能力。

## 架构

### 模块边界

建议逐步从 `.cowork-flow/scripts/task.py` 和零散 validator 中抽出以下模块：

```text
.cowork-flow/scripts/common/gates.py
.cowork-flow/scripts/common/state_machine.py
.cowork-flow/scripts/common/tdd_evidence.py
.cowork-flow/scripts/common/test_intent.py
.cowork-flow/scripts/common/coding_standards.py
.cowork-flow/scripts/common/git_snapshot.py
```

其中：

- `gates.py` 定义 `GateResult`、`GateRunner`、阶段入口。
- `state_machine.py` 定义合法状态迁移和 gate 执行顺序。
- `tdd_evidence.py` 读取和验证 `tdd.jsonl`。
- `test_intent.py` 识别浅层测试和缺失行为映射。
- `coding_standards.py` 校验 UTF-8 和编码规范。
- `git_snapshot.py` 统一收集 modified、staged、untracked 文件。

### 状态迁移设计

现有 lifecycle 命令先保留 CLI 入口，但内部改为：

```text
cmd_review -> StateTransitionService.transition(task, "review")
cmd_complete -> StateTransitionService.transition(task, "completed")
```

`StateTransitionService` 负责：

1. 读取任务状态。
2. 校验当前状态是否允许迁移。
3. 调用对应 gate runner。
4. 对 block 结果非 0 退出。
5. 原子写入任务状态。
6. 写入 gate/audit 事件。

### Gate 接入点

```text
task start:
  planning readiness
  L2 proposal/spec/design/plan/task link

task review:
  implementation scope
  TDD evidence
  test intent
  coding standards

task complete:
  check evidence
  test intent review
  coding standards
  spec/template sync

task archive:
  completed status
  linked change consistency
  dirty scope
```

### Skill 设计

新增 `tdd` skill：

```text
.agents/skills/tdd/SKILL.md
template/.agents/skills/tdd/SKILL.md
```

触发顺序：

```text
start -> before-dev -> tdd -> implement -> check
```

`tdd` skill 只指导执行方法，不负责强制。强制由 runtime gate 完成。

### 测试意图审查设计

实现分两层：

1. 静态反模式扫描：识别 `assert True`、import-only、函数存在、mock-only、空 snapshot。
2. 证据审查：要求每个 TDD evidence 说明 `whyThisTestMatters`，并映射 PRD acceptance id。

第一阶段先用启发式阻断明显无意义测试，后续再增强为更深的 mutation-like 检查。

### 编码规范校验设计

编码规范校验读取统一 git snapshot，不再只依赖 `git diff --name-only`。必须覆盖：

- working tree modified
- staged changes
- untracked files

Python runtime 自身所有文件读写必须显式 `encoding="utf-8"`，避免校验器自身违反项目编码规范。

## 迁移策略

1. 先修复现有校验脚本的 UTF-8 与运行时错误。
2. 引入 `GateResult`，让旧 validator 包装成统一结果。
3. 将 `task review` / `task complete` 改为 gate 阻断。
4. 新增 TDD evidence 与 tdd skill。
5. 增加测试意图和编码规范 gate。
6. 最后抽出状态机服务，减少 `task.py` 直接写状态。

## 风险与缓解

- 风险：一次性改造面过大。缓解：按 gate 接入点分阶段提交，每阶段保留回归测试。
- 风险：启发式测试意图检查误伤。缓解：第一版只 block 明显无意义模式，其他输出 warn。
- 风险：root/template 漂移。缓解：每个实现任务都明确 root/template 文件归属和同步测试。
- 风险：Windows 编码问题再次出现。缓解：所有 Python 文件读写显式 UTF-8，PowerShell 验证命令显式设置输出编码。

## 验证命令

```powershell
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
.\.cowork-flow\run.cmd task validate .cowork-flow/tasks/06-23-tdd-productization
.\.cowork-flow\run.cmd change validate 06-23-tdd-productization
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```
