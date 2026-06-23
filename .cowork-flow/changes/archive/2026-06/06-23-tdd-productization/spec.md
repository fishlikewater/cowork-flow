# TDD 产品化与门禁行为规格

## 目标

定义 `cowork-flow` 在行为变更任务中的 TDD、测试意图、编码规范和状态迁移强约束。该规格用于指导 runtime、skills、固定代理提示和测试套件实现。

## 行为规则

### Gate Result

所有门禁校验必须输出统一结构：

```json
{
  "status": "pass|warn|block",
  "stage": "review",
  "ruleId": "TDD-RED-001",
  "message": "行为变更缺少 red 证据",
  "evidence": "tdd.jsonl missing AC-001 red output",
  "fixHint": "先写失败测试并记录 TDD evidence"
}
```

- `block` 必须导致当前 lifecycle 命令非 0 退出。
- `warn` 必须展示并记录，但不阻断状态迁移。
- `pass` 可作为审计证据写入 gate 报告。

### 状态迁移

任务状态必须通过统一状态机迁移：

```text
planning -> in_progress -> review -> completed -> archived
```

每次状态迁移按顺序执行：

```text
load state -> run gates -> append audit event -> atomic write -> print next action
```

业务命令不得绕过 gate 直接写 `task.json.status`。

### TDD 证据

行为变更、bug 修复、状态机、协议、CLI 输出契约、权限、数据格式、错误处理改动必须提供 TDD 证据。证据文件为：

```text
.cowork-flow/tasks/<task>/tdd.jsonl
```

每条记录至少包含：

```json
{
  "acceptanceId": "AC-001",
  "testFile": "tests/test_xxx.py",
  "testName": "test_xxx",
  "redCommand": "python -m unittest ...",
  "redExitCode": 1,
  "redOutputExcerpt": "...",
  "failureReason": "...",
  "whyThisTestMatters": "...",
  "greenCommand": "python -m unittest ...",
  "greenExitCode": 0,
  "broaderVerification": "npm run test:all"
}
```

`task review` 必须阻断以下情况：

- 缺少 `tdd.jsonl` 且任务不是明确豁免类型。
- `redExitCode` 为 0。
- `greenExitCode` 非 0。
- red 失败原因是语法、导入、环境或测试设置问题，而不是目标行为。
- TDD 证据未映射 PRD 验收标准。

### 测试意图审查

有效测试必须至少证明以下一种行为：

- PRD 验收标准
- bug 回归
- 状态迁移
- 错误边界
- CLI/runtime 可观察行为
- 持久化或文件输出契约
- 跨层协议

以下测试不得满足 TDD gate：

- `assert True`
- import-only 测试
- 只断言函数存在
- 只断言 mock 被调用而无行为断言
- 空 snapshot
- 与实现细节同义的测试
- 删除目标业务规则后仍会通过的测试

`cowork-check` 必须输出 `test_intent_review`，说明关键测试如何在目标行为破坏时失败。

### 编码规范门禁

编码规范校验必须覆盖新增、修改、staged 和 untracked 文件。第一批 block 规则：

- Python 文本读写必须显式 `encoding="utf-8"`。
- PowerShell 文本读写必须显式 `-Encoding UTF8` 或等价 UTF-8 对象。
- Node 文件读写必须显式 `utf8`。
- Windows 输出编码初始化必须显式设置 UTF-8。
- 默认编码、隐式 open、隐式文本 subprocess 输出读取不得进入 complete。

### 豁免

纯文档、注释、格式化、无行为影响的模板文字调整可豁免 TDD，但必须记录：

- 豁免类型
- 不需要 TDD 的原因
- 替代验证命令

## 验收标准

- `task review` 能阻断缺少 TDD 证据的行为变更。
- `task review` 能阻断浅层无意义测试。
- `task complete` 能阻断编码规范 blocker。
- 直接从 `in_progress` complete 失败。
- 产品级测试覆盖 gate 输出、状态迁移、证据文件和 Windows 路径。
