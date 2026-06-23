# TDD 产品化与门禁改造 Implementation Plan

> For formal fixed-agent work: create a runtime context with `.cowork-flow/run subagent init`, pass `cowork_runtime_context_id: <runtime_context_id>` through the active Host Adapter, then dispatch `cowork-implement` or `cowork-check`. Close the runtime context after verification.

**Goal:** 将 TDD、测试意图、编码规范和流程状态推进从提示词约定升级为 runtime 可阻断的产品级门禁。

**Architecture:** 保留 Node CLI 负责安装和分发，Python runtime 负责 workflow 状态机、gate、validator 和审计。新增 `tdd` skill 指导 AI 执行 red-green-refactor，但最终由 `task review` / `task complete` 的 Gate Engine 强制验收。

**Verification:** 每个任务先跑 focused regression，再跑相关 broader validation；整合阶段至少运行 `git diff --check`、`python -m unittest discover tests -v`、`npm test`、`npm run test:template`、`npm run pack:check`。

## Execution Strategy

串行执行。原因：多个任务会共享 `.cowork-flow/scripts/task.py`、runtime common 模块、workflow 文档、template 镜像和测试套件。可以在 GateResult 模型稳定后，将 `tdd skill` 文档同步和产品级验收套件补充拆成低冲突并行切片，但最终必须做一次集成验证。

## Scope

### In Scope

- `.cowork-flow/scripts/common/*` 新增或重构 gate、状态机、TDD、测试意图和编码规范校验。
- `.cowork-flow/scripts/task.py` 接入 review/complete 强门禁。
- `.agents/skills/tdd/SKILL.md` 与 `template/.agents/skills/tdd/SKILL.md`。
- `.agents/skills/before-dev`、`writing-plans`、`check`、固定代理提示中对 TDD 的引用。
- `.cowork-flow/workflow.md`、`.cowork-flow/spec/` 与 template 镜像。
- `tests/` 与 `test/` 中的产品级验收。

### Out of Scope

- 不重写 Node CLI 的安装分发架构。
- 不替换 host adapter 协议。
- 不强制纯文档、格式化、注释改动使用 TDD。

## Acceptance Mapping

每个 PRD 验收标准必须使用稳定 ID，格式为 `AC-001`。所有 TDD evidence 的 `acceptanceId` 必须引用这些 ID；没有稳定验收 ID 的测试证据不能满足 review gate。

## Tasks

### 1. Gate Engine 与状态迁移门禁

Task: `.cowork-flow/tasks/06-23-gate-engine-state-machine`

Files:

- `.cowork-flow/scripts/common/gates.py`
- `.cowork-flow/scripts/common/state_machine.py`
- `.cowork-flow/scripts/task.py`
- `template/.cowork-flow/scripts/common/gates.py`
- `template/.cowork-flow/scripts/common/state_machine.py`
- `template/.cowork-flow/scripts/task.py`
- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`

Steps:

1. 先写失败测试：从 `in_progress` 直接 complete 或 gate 返回 block 时，命令必须非 0。
2. 新增 `GateResult` / `GateRunner`。
3. 将旧 readiness / rules validator 包装为 gate result。
4. 接入 `task review` 和 `task complete`。
5. 保留 `task next` 只读行为。

Verification:

```powershell
python -m unittest tests.test_flow_script_paths tests.test_workflow_parallel_sessions -v
.\.cowork-flow\run.cmd task next .cowork-flow/tasks/06-23-gate-engine-state-machine
```

Expected result: block gate 会阻断状态迁移，合法规划任务的 `task next` 仍只读。

### 2. TDD Skill 与 TDD Evidence

Task: `.cowork-flow/tasks/06-23-tdd-skill-evidence`

Files:

- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.agents/skills/before-dev/SKILL.md`
- `.agents/skills/writing-plans/SKILL.md`
- `.codex/agents/cowork-implement.toml`
- `template/.codex/agents/cowork-implement.toml`
- `.cowork-flow/scripts/common/tdd_evidence.py`
- `template/.cowork-flow/scripts/common/tdd_evidence.py`
- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_cowork_agents.py`

Steps:

1. 先写失败测试：行为变更任务缺少 `tdd.jsonl` 时，`task review` 必须失败。
2. 新增 `tdd` skill，要求 AI 产出 red-green-refactor evidence。
3. 实现 `tdd.jsonl` 读取和字段校验。
4. 更新 `cowork-implement` 固定代理提示，要求实现前产出 TDD evidence 或记录豁免。
5. 将 TDD gate 接入 `task review`。
6. 同步 root/template skill 和固定代理提示。

Verification:

```powershell
python -m unittest tests.test_flow_script_paths tests.test_workflow_parallel_sessions tests.test_cowork_agents -v
```

Expected result: 缺少 TDD 证据的行为变更无法进入 review；纯文档豁免必须有明确原因。

### 3. 测试意图审查门禁

Task: `.cowork-flow/tasks/06-23-test-intent-review-gate`

Files:

- `.cowork-flow/scripts/common/test_intent.py`
- `template/.cowork-flow/scripts/common/test_intent.py`
- `.agents/skills/check/SKILL.md`
- `template/.agents/skills/check/SKILL.md`
- `.codex/agents/cowork-check.toml`
- `template/.codex/agents/cowork-check.toml`
- `tests/test_flow_script_paths.py`
- `tests/test_cowork_agents.py`

Steps:

1. 先写失败测试：`assert True`、import-only、函数存在、mock-only 测试不能满足 TDD gate。
2. 新增测试意图 validator，第一阶段 block 明显无意义测试，复杂疑点输出 warn。
3. 要求 `cowork-check` 输出 `test_intent_review`。
4. 接入 `task review` 和 `task complete`。

Verification:

```powershell
python -m unittest tests.test_flow_script_paths tests.test_cowork_agents -v
```

Expected result: 浅层测试被阻断，check 阶段必须解释关键测试如何抓住目标回归。

### 4. 编码规范强约束与 UTF-8 校验

Task: `.cowork-flow/tasks/06-23-coding-standards-gate`

Files:

- `.cowork-flow/scripts/common/coding_standards.py`
- `.cowork-flow/scripts/common/git_snapshot.py`
- `.cowork-flow/scripts/common/validate_coding_standards.py`
- `.cowork-flow/scripts/common/validate_rules.py`
- `template/.cowork-flow/scripts/common/*`
- `.cowork-flow/spec/backend/encoding-guidelines.md`
- `tests/test_flow_script_paths.py`
- `tests/fixtures/coding-standards/implicit-open.py`
- `tests/fixtures/coding-standards/implicit-read-file.js`
- `tests/fixtures/coding-standards/implicit-get-content.ps1`
- `test/coding-standards.test.js`

Steps:

1. 先写失败测试：Python `open()` 未显式 encoding、Node `readFile` 未显式 utf8、PowerShell `Get-Content` 未显式 Encoding 时 gate block。
2. 修复现有 validator 自身的隐式默认编码。
3. 统一 git snapshot，覆盖 modified、staged、untracked 文件。
4. 将编码规范 gate 接入 `task review` / `task complete`。

Verification:

```powershell
python -m unittest tests.test_flow_script_paths -v
npm test -- coding-standards
git diff --check
```

Expected result: 编码违规不能进入 complete；validator 在 Windows 下不依赖系统默认编码。

### 5. 产品级验收套件与模板同步

Task: `.cowork-flow/tasks/06-23-product-validation-suite`

Files:

- `tests/test_flow_script_paths.py`
- `tests/test_workflow_parallel_sessions.py`
- `tests/test_cowork_agents.py`
- `tests/test_host_adapters.py`
- `test/*.test.js`
- `scripts/run-template-tests.js`
- `scripts/pack-check.js`
- `.cowork-flow/workflow.md`
- `template/.cowork-flow/workflow.md`
- `.cowork-flow/spec/workflow-state-templates.md`
- `template/.cowork-flow/spec/workflow-state-templates.md`
- `.agents/skills/tdd/SKILL.md`
- `template/.agents/skills/tdd/SKILL.md`
- `.agents/skills/before-dev/SKILL.md`
- `template/.agents/skills/before-dev/SKILL.md`
- `.agents/skills/writing-plans/SKILL.md`
- `template/.agents/skills/writing-plans/SKILL.md`
- `.agents/skills/check/SKILL.md`
- `template/.agents/skills/check/SKILL.md`
- `.codex/agents/cowork-implement.toml`
- `template/.codex/agents/cowork-implement.toml`
- `.codex/agents/cowork-check.toml`
- `template/.codex/agents/cowork-check.toml`

Steps:

1. 确认前四个实现任务已经各自包含 focused failing tests；本任务只补齐跨任务端到端验收，不替代前置 TDD red 阶段。
2. 覆盖 happy path：create/start/review/complete/archive。
3. 覆盖 skip path：无 review 直接 complete 必须失败。
4. 覆盖 TDD missing path：行为变更无 evidence 必须失败。
5. 覆盖 shallow test path：无意义测试不能满足 gate。
6. 覆盖 coding violation path：编码违规必须失败。
7. 覆盖 fresh install/template path。
8. 覆盖 Windows `run.cmd` 路径。

Verification:

```powershell
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```

Expected result: 产品级验收覆盖流程跳步、TDD、测试意图、编码规范、模板同步和安装面。

## Final Integrated Verification

```powershell
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
.\.cowork-flow\run.cmd change validate 06-23-tdd-productization
.\.cowork-flow\run.cmd task validate .cowork-flow/tasks/06-23-tdd-productization
python -m unittest discover tests -v
npm test
npm run test:template
npm run pack:check
git diff --check
```

## Remaining Risks

- 第一阶段测试意图检查只能阻断明显无意义测试，后续需要根据误报/漏报继续增强。
- Gate Engine 和状态机改造会触及共享生命周期命令，必须小步提交并保持 focused tests。
- `npm run test:all` 在 Windows 环境可能受 hook entrypoint 影响，应保留 run.cmd 级 focused validation 作为定位依据。
