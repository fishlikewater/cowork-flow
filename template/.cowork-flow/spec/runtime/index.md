# Runtime Specs

本目录存放 workflow runtime 直接读取的机器配置。

- `contract-registry.json`: hook/plugin 注入 contract digest 的注册表。
- `host-assets.json`: 宿主平台、资产归属、技能目标、同步保护策略和旧资产迁移清单的单源；结构由 `../schemas/host-assets.schema.json` 约束。

缺少或损坏的 runtime 文件不能静默放行关键流程能力。宿主插件可使用最小 fallback
避免崩溃，但必须在 digest 中暴露 warning；doctor/tests 负责发现缺失。

用户自然语言规范不在本目录注册；`task-review` skill 直接读取
`spec/backend/`、`spec/frontend/`、`spec/guides/` 并输出审查结论。

运行时写入边界：

- CLI/宿主/Git 适配层位于 `scripts/adapters/`，用例服务位于 `scripts/services/`。
- JSON 状态通过 `scripts/infra/storage/` 读写并显式使用 UTF-8。
- init/sync 通过 Asset Plan、staging、备份和 rollback 提交资产，版本文件最后更新。
- 旧状态只允许在带迁移测试的读取边界兼容；新写入必须使用当前 schema 和权威路径。
