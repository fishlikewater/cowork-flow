# References — 按需加载参考材料

> **不自动加载。** 仅当 skill 入口显式引用 reference ID 时、或 agent 判断需要时读取。

本目录存放窄适用范围的快速参考卡，作为 skill 入口的补充。相较 `spec/contracts/`（契约）和 `spec/backend|frontend/`（域规范），reference 文件之作用是：
1. 在 check / finish 阶段提供快速对照清单（而非完整规范）
2. 在分析潜在 prompt injection 时提供防御规则集
3. 声明性总结 cowork-flow 已实现的协作模式

加载规则：
- contract-registry.json 的 `references[*].loadWhen` 之一被匹配时
- skill 正文中显式引用 reference ID 时
- 用户在主会话请求特定检查时（如"security checklist"）
- **不**自动加载——这是与 contracts/ 系列的区别

当前参考：
- [definition-of-done.md](definition-of-done.md) — DoD：项目级完成门槛（L0/L1/L2 三档）
- [testing-checklist.md](testing-checklist.md) — 测试结构/深度/反模式快速参考
- [security-checklist.md](security-checklist.md) — OWASP Top 10 映射 + 快速检查
- [orchestration-patterns.md](orchestration-patterns.md) — 已实现的协作模式声明性目录
