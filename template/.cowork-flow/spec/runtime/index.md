# Runtime Specs

本目录存放 workflow runtime 直接读取的机器规范。

- `rules.json`: workflow rule 元数据单源。执行器可以按 rule id 做事实判断，
  但 violation 的 `message`、`severity`、`fix_hint` 和来源信息必须来自这里。
- `contract-registry.json`: hook/plugin 注入 contract digest 的注册表。
- `host-assets.json`: 宿主平台、资产归属、技能目标、同步保护策略和旧资产迁移清单的单源；结构由 `../schemas/host-assets.schema.json` 约束。

缺少或损坏的 runtime 文件不能静默放行关键门禁。宿主插件可使用最小 fallback
避免崩溃，但必须在 digest 中暴露 warning；doctor/tests 负责发现缺失。

运行时写入边界：

- 命令层通过 `scripts/application/` 调用任务与 runtime context 用例。
- JSON 状态通过 `scripts/common/storage/` 读写并显式使用 UTF-8。
- init/sync 通过 Asset Plan、staging、备份和 rollback 提交资产，版本文件最后更新。
- 旧状态只允许在带迁移测试的读取边界兼容；新写入必须使用当前 schema 和权威路径。
