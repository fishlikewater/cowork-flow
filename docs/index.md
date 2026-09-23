# cowork-flow 文档

三份文档，各自回答一类问题：

| 文档 | 回答什么 |
|---|---|
| [architecture.md](architecture.md) | 仓库怎么分层、`template/` 与 `presets/` 各是什么、规范挂命令（spec-check）怎么工作、接入一个项目该遵循什么原则 |
| [hosts.md](hosts.md) | 每个宿主怎么接（插件 / 预设 / hook）、装到哪个目录、项目技能从哪被发现、每个宿主支持哪些图标字段、有哪些环境变量 |
| [release.md](release.md) | 测试怎么分层、发布流程与 CI 通道、维护者命令（`source:refresh`、`icons:export`） |

用户侧的入口是 [README](../README.md)；版本内容见 [CHANGELOG](../CHANGELOG.md)；怎么参与见 [CONTRIBUTING](../CONTRIBUTING.md)。

## 权威顺序

文档会滞后，代码不会。冲突时以这些为准：

| 问题 | 权威来源 |
|---|---|
| 当前能执行什么命令、下一步该做什么 | `./.cowork-flow/run task next --json` |
| 命令面（命令、旗标、别名、退出码） | `src/commands/registry.js`（帮助文本由它生成） |
| 宿主资产归属、技能读取根与发现通道、机器级载荷声明 | `template/.cowork-flow/spec/runtime/host-assets.json` |
| 宿主适配契约（注入、子代理派发、事实层访问……） | `template/.cowork-flow/spec/contracts/` |
| 插件身份（名称、简介、作者、品牌色、图标路径） | `presets/plugin-meta.json` |
| 版本内容 | `CHANGELOG.md` |

`README.md` 里的命令表由 `test/cli-registry.test.js` 对着注册表守；`docs/` 与 `README.md` 的相对链接由 `test/docs.test.js` 守。
