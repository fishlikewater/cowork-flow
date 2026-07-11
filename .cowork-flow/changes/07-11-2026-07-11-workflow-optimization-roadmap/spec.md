# Workflow Optimization Roadmap Spec

## Contract: optimization execution

- 每个任务必须先运行 `task next <task>` 或等价只读检查确认状态。
- 行为变化任务必须先补可失败的回归测试，再实现。
- 文档、计划和任务创建可以作为 L0/L1 准备工作，但不得宣称 runtime 行为已改变。
- 涉及 root/template 的任务必须在 PRD 中明确同步边界。
- 涉及正式子代理的任务必须遵守 `.cowork-flow/spec/core/dispatch.md`：主会话协调，子代理叶子执行，runtime context 绑定是接受门禁。

## Contract: release health

发布前健康检查至少覆盖：

1. `git diff --check`。
2. UTF-8/BOM 扫描。
3. root/template 同步检查。
4. package files/pack 边界检查。
5. DB migration status 或 dry-run。
6. host adapter/subagent safety 检查。
7. Node 与 Python 关键测试。

## Contract: state authority

- DB `runtime_context` 和 `runtime_session` 是正式运行时状态权威。
- 旧 `.runtime` 文件态不得新增写入口；如仍需读取，必须标注为兼容、诊断或迁移路径。
- 文档、skills、agent assets 不得把旧文件态描述为当前权威。

## Contract: root/template parity

- 分发面文件必须有可测试的同步关系。
- 允许差异必须显式列入清单，并说明原因。
- 生成文件、缓存文件、runtime 本地状态、archive 历史记录不得参与强同步。

## Contract: service extraction

- 拆分 `task.py` 或 `flow/store.py` 时，命令行入口、退出码和现有公开行为默认保持兼容。
- 新模块必须有行为级测试，不允许只断言函数存在或 mock 被调用。
- 每次拆分必须同时处理 root 与 template，或在 PRD 中说明为什么只改一侧。