# 参与开发

感谢你参与 cowork-flow。本文只保留开始工作、判断改动范围和提交 PR 需要知道的内容。仓库结构见 [架构与扩展](docs/architecture.md)，发布流程见 [发布与维护](docs/release.md)。

## 环境要求

| 依赖 | 版本 | 用途 |
|---|---|---|
| Node.js | 20 或更高 | CLI 与 Node 测试 |
| Python | 3.10 | 模板运行时与 Python 测试 |
| Git | 当前稳定版 | 任务基线、同步和宿主测试 |

仓库没有运行时依赖，也没有 devDependency。`npm ci` 不会安装第三方包；新增依赖前先说明原因并讨论方案。

所有源码和文档使用 UTF-8。Windows 脚本与 POSIX 脚本的行尾契约由 `.gitattributes` 管理，不要手工改写。

## 本地起步

```bash
git clone https://github.com/fishlikewater/cowork-flow.git
cd cowork-flow
npm ci
npm run source:refresh
```

`source:refresh` 会从 `template/` 刷新本仓库自己的 `.cowork-flow/`、`.agents/skills/` 和 `.claude/skills/`。改过 `template/` 后必须重跑，否则本地测试和 `./.cowork-flow/run` 仍使用旧副本。

本仓库也使用 cowork-flow。开始修改前先查看当前状态：

```bash
./.cowork-flow/run task next --json
```

`AGENTS.md` 和 `.cowork-flow/spec/` 是实现约束，不要绕开当前任务另建一套流程。

## 先判断改哪里

| 改动 | 主要位置 |
|---|---|
| 项目初始化后写入的文件 | `template/` |
| 机器级插件、预设和 hook | `presets/` |
| CLI 命令与安装器 | `src/commands/`、`src/lib/` |
| 项目运行时 | `template/.cowork-flow/scripts/` |
| 宿主、同步和技能声明 | `template/.cowork-flow/spec/runtime/host-assets.json` |
| Node 测试 | `test/` |
| Python 测试 | `tests/` |
| 用户和维护文档 | `README.md`、`docs/`、`CONTRIBUTING.md` |

新增或修改行为时，先补一个能失败的测试，再写最小实现。重构前先固定现有行为，避免顺手改动无关模块。

## 宿主改动

接入或修改宿主时，通常需要同时检查：

| 位置 | 内容 |
|---|---|
| `template/.<host>/` | 需要随项目落盘的 hook、agents、commands 和配置 |
| `template/.cowork-flow/adapters/<host>/adapter.yaml` | 适配器与技能发现声明 |
| `template/.cowork-flow/spec/runtime/host-assets.json` | 平台、载荷、同步策略和迁移清单 |
| `presets/<host>/` | 插件、预设或机器级 hook |
| `src/commands/install-<host>-*.js`、`src/commands/registry.js` | 安装、卸载和命令注册 |
| `test/host-assets.test.js`、`test/host-command.test.js`、`test/<host>-plugin.test.js`、`tests/test_host_*.py` | 行为与回归门禁 |
| `docs/hosts.md` | 安装前提、升级、卸载和排障 |

上表说明改哪里。宿主特化不能进入通用层——具体边界见 [架构与扩展](docs/architecture.md) 的“扩展规则”。

## 提交信息

使用 Conventional Commits：

```text
<type>(<scope>): <中文描述>
```

示例：

```text
feat(host): 接入 Qoder 宿主
fix(host): 修正技能发现路径
refactor(zcode): 将插件载荷迁到 presets/zcode
```

常用 `type`：`feat`、`fix`、`refactor`、`docs`、`test`、`chore`、`perf`。描述写清楚做了什么，不写“优化体验”一类无法核对的信息。

## 测试与 PR 前置检查

最低检查：

```bash
npm run test:fast
git diff --check
```

按改动范围该补哪些命令、各自覆盖什么，见 [发布与维护](docs/release.md) 的“发布前检查”——那是命令与适用场景的唯一清单，本文不重复。

`test:fast` 只运行 `package.json` 中列出的核心套件。新增测试文件时，根据影响面决定是否加入该列表。

平台前提不满足时，测试可能明确跳过。CI 在 Ubuntu 和 Windows 上运行各自的门禁，本地缺少平台前提可以跳过，但必须如实记录，不能把跳过写成通过。

PR 描述需要写明：

- 改了什么，以及为什么这样改。
- 运行过哪些测试及结果。
- 哪些平台用例跳过或仍未验证。
- 是否改变安装位置、命令、配置格式或升级步骤。

## 许可

提交代码即表示同意以 [MIT](LICENSE) 授权。
