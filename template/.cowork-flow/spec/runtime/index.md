# Runtime Specs

本目录存放 workflow runtime 直接读取的机器规范。

- `rules.json`: workflow rule 元数据单源。执行器可以按 rule id 做事实判断，
  但 violation 的 `message`、`severity`、`fix_hint` 和来源信息必须来自这里。
- `contract-registry.json`: hook/plugin 注入 contract digest 的注册表。

缺少或损坏的 runtime 文件不能静默放行关键门禁。宿主插件可使用最小 fallback
避免崩溃，但必须在 digest 中暴露 warning；doctor/tests 负责发现缺失。
