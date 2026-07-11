# Workflow Optimization Roadmap Design

## 架构原则

1. **DB 状态优先**：`runtime_context`、`runtime_session`、task 状态和 dashboard 进程状态继续以 DB 为权威；历史文件态只能作为迁移/诊断对象，不能新增写入口。
2. **模板分发面可验证**：根目录实现和 `template/` 实现的同步关系必须可被脚本和测试验证，而不是依赖人工记忆。
3. **CLI 薄化**：命令脚本保留参数解析、输出和退出码；生命周期、存储、诊断、宿主契约判断尽量下沉到可测试服务/纯函数。
4. **先门禁后重构**：先补 doctor、sync gate 和契约测试，再拆大文件，避免重构期间失去保护网。
5. **文档跟随 runtime**：workflow/spec/skills/README 的文字必须反映实际运行时，不用文档承诺尚未实现的行为。

## 分期设计

### P0：规划基线与风险盘点

交付一份 baseline 报告，固定后续任务的判断依据：

- 状态权威矩阵：列出 active task、runtime context、runtime session、task lifecycle、archive、journal、dashboard 的读写入口。
- 文件复杂度表：列出 `task.py`、`flow/store.py`、`party_mode_v2.py`、`doctor.py`、宿主插件和测试文件的行数、职责和拆分候选。
- root/template 差异表：列出应同步文件、允许差异文件和当前漂移。
- 测试覆盖基线：列出现有 Node/Python 测试与缺失契约。
- 风险排序：将后续 P1/P2/P3 工作按收益、风险和依赖排序。

### P1-A：doctor 与发布前健康检查

目标是让维护者在动手前能看到明确问题：

- `doctor` 增加或整理 `--release-health` 检查。
- 输出编码/BOM、DB migration、host adapter、subagent safety、root/template sync、pack 边界的状态。
- 错误输出使用“当前状态 / 阻塞原因 / 下一条命令 / 涉及文件”结构。
- `pack:check` 或等价发布检查接入必要健康项。

### P1-B：root/template 同步强门禁

目标是把历史 root/template 漂移变成可阻断问题：

- 建立同步清单和允许差异清单。
- 增加 sync check 命令或扩展现有 `scripts/pack-check.js` / `test/sync.test.js`。
- 覆盖 `.cowork-flow/scripts`、`.cowork-flow/spec`、`.agents/skills`、宿主资产、NPM package 边界。
- 对生成目录、runtime 目录、pycache、历史 archive 明确排除。

### P1-C：运行时状态权威收敛

目标是把“谁读写状态”讲清并减少兼容路径：

- 审计 `active_task.py`、`execution_context.py`、`subagent.py`、`task.py`、`flow/store.py`、宿主插件和 hooks。
- 对仍存在的文件态读写分成三类：必须保留、可迁移、应删除。
- 先补测试证明 fail-closed 和 DB 权威，再做最小收敛。
- 更新 spec/core 与宿主资产，避免文档继续引用已废弃状态文件。

### P2-A：任务生命周期服务层拆分

目标是降低 `task.py` 修改成本：

- 从 `task.py` 提取生命周期服务、上下文服务、pattern adapter、输出格式辅助。
- 保持命令行参数和文本输出兼容，除非 PRD 明确要求优化输出。
- 新增/更新测试覆盖 planning -> in_progress -> review -> completed -> archive、blocked/unblocked、pattern transition。
- root/template 同步更新。

### P2-B：FlowStore 存储与迁移边界拆分

目标是降低 `flow/store.py` 的存储层复杂度：

- 拆分 schema/migration、task repository、runtime repository、dashboard repository 或等价边界。
- 保持 SQLite schema 和迁移行为兼容。
- 增加 migration dry-run/status、旧库样本、事务边界和 checksum 相关测试。
- 不在同一任务中改变 task lifecycle 语义。

### P2-C：正式子代理宿主契约测试

目标是把宿主差异和安全边界放入回归测试：

- 覆盖 Codex、Claude Code、OpenCode 的 entry signal / env / command 文本 / bind 示例。
- 覆盖 runtime context missing、closed、mismatched、duplicate bind、host context missing。
- 覆盖 fixed agent 禁止事项：不能 start/resume/archive/commit/spawn。
- 覆盖 main session 验收：dispatch payload 不等于 child created，child output 不等于 accepted，close 后无 stray session。

### P3：文档与新用户闭环

目标是让新用户和维护者都能快速理解系统：

- README 变成入口页，拆出快速上手、维护者指南、运行时契约、宿主适配器开发指南。
- 增加最小闭环 demo：init -> L0 task -> check -> complete/archive -> add-session。
- 增加 Mermaid 状态图：change/plan/task/runtime_session/runtime_context/journal/archive。
- 文档必须引用真实命令，并通过 smoke check 验证关键命令仍存在。

## 执行策略

总体串行：P0 -> P1-A/P1-B -> P1-C -> P2-A/P2-B/P2-C -> P3。

可并行的低冲突切片：

- P1-A doctor 与 P1-B sync gate 可以并行，但合并后必须执行 `npm run test:all`、Python 测试和 `git diff --check`。
- P2-C 契约测试可以先只加失败/保护测试，与 P2-A/P2-B 的实现拆分错开合并。
- P3 文档必须等 P1/P2 的命令和边界稳定后再做最终文本重构。

## 关键风险

- 当前工作区已有大量未提交改动：每个任务开始前必须运行 `git status --short`，只纳入本任务文件。
- root/template 双份代码容易漏改：每个任务必须说明是否需要同步 template。
- 重构可能改变 CLI 输出：除非 PRD 明确，否则保持输出兼容。

## 关键假设

- workflow/spec/skills/host assets 必须跟随真实 runtime，不用文档掩盖未实现行为。
- 发布质量优先级高于拆分速度；没有 sync gate 和契约测试保护的重构不得启动。
- 所有 root/template 相关任务默认需要同步两侧，除非 PRD 明确说明只改一侧的原因。
- DB 迁移风险高：FlowStore 拆分必须先补旧库样本和 migration 回归。