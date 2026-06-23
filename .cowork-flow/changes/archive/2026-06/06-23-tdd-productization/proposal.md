# TDD 产品化与门禁改造

## 目标

将 `cowork-flow` 从依赖文档、提示词和 AI 自觉执行的流程模板，升级为可落地交付的工作流产品码。行为变更、编码规范、TDD 证据、测试意图审查和任务状态推进必须由 runtime gate 强约束，而不是只由 skill 或 workflow 文档提醒。

## 用户价值

- 主会话和固定代理即使理解不完整，也不能跳过关键流程步骤。
- 行为变更必须先证明测试会失败，再实现并证明测试变绿。
- Review 不只检查是否执行过命令，还检查测试是否真的保护业务行为。
- 编码规范尤其是 UTF-8 读写要求可以被机器阻断，减少 Windows/PowerShell 环境下的乱码和隐式默认编码问题。
- 后续发布的模板项目具备一致的产品级 workflow 质量，而不是靠项目维护者反复口头纠偏。

## 非目标

- 不在本次计划中替换 Node CLI 的安装/分发职责。
- 不要求所有文档、格式、注释类改动都强制 TDD。
- 不把测试覆盖率作为唯一质量指标。
- 不把所有规则都一次性做成完美静态分析器；第一阶段优先覆盖可验证的硬门禁。

## 关键假设

- 当前 `cowork-flow` 仍采用 Node CLI 分发模板、Python runtime 执行 workflow 命令的双层架构。
- 正式实现和检查仍走固定 `cowork-implement` / `cowork-check` 协议；runtime gate 是最终强约束。
- root 与 `template/` 的 workflow 资产在过渡期仍需保持同步。
- L1/L2 行为变化、bug 修复、状态机/协议/CLI 契约变化必须具备 TDD 证据；纯文档和格式调整可记录豁免原因。

## 范围边界

### 范围内

- 新增统一 Gate Engine 和门禁结果模型。
- 新增 TDD evidence 数据文件、校验器和 `tdd` skill。
- 新增测试意图审查规则，阻断浅层无意义测试。
- 将编码规范从提示升级为可执行校验。
- 将 `task review` / `task complete` 接入强制门禁。
- 增加产品级端到端验收套件。
- 同步 root/template 资产和对应测试。

### 范围外

- 不重写全部 CLI。
- 不迁移到单一语言运行时。
- 不改造宿主适配器协议本身，除非 gate 集成需要读取已有 adapter 元数据。
- 不在规划阶段启动具体实现任务。

## 推荐方向

采用 `skill + runtime gate` 双层策略：

1. `tdd` skill 指导 AI 以 red-green-refactor 方式工作。
2. runtime gate 验收 TDD 证据、测试意图和编码规范。
3. 状态机统一控制 `planning -> in_progress -> review -> completed -> archived`。
4. `cowork-check` 专门攻击测试质量，不能只接受“测试通过”。

## 被拒方案

- 只在 `workflow.md` 增加 TDD 文案：无法阻止 AI 跳步。
- 只新增 `tdd` skill：能改善行为，但不能形成产品级强约束。
- 只要求覆盖率：容易被无意义测试刷指标，无法证明业务意图。
- 一次性重写全部 runtime：风险高，难以分阶段验证。

## 验收标准

- 行为变更缺少有效 TDD red-green 证据时，`task review` 返回非 0。
- 无意义测试不能满足 TDD gate。
- 编码规范违规不能进入 `task complete`。
- 未经过 review/check 阶段直接 complete 必须失败。
- `cowork-check` 输出测试意图审查结论。
- root/template 中新增 skill、workflow、spec、hook 相关资产保持同步。
- 端到端测试覆盖 happy path、跳步失败、TDD 缺失、无意义测试、编码违规、fresh install 和 Windows `run.cmd` 路径。
