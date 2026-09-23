# 参与开发

## 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Node.js | `>= 20`（`package.json` 的 `engines`） | CLI 与全部 Node 测试 |
| Python | 3.10（CI 使用的版本） | 模板集成测试与仓库级 pytest |
| Git | — | 模板与宿主适配的测试会用真实仓库状态 |

仓库**零运行时依赖、零 devDependency**：`npm ci` 只读 `package-lock.json`，不装任何第三方包。给 `src/`、`template/`、`presets/` 引入依赖的 PR 不会被接受。

## 起步

```bash
git clone https://github.com/fishlikewater/cowork-flow.git
cd cowork-flow
npm ci
npm run source:refresh      # 物化被忽略的根 .cowork-flow/、.agents/skills/、.claude/skills/
```

`source:refresh` 以 `template/.cowork-flow/` 和 `template/skills/` 为唯一 tracked 分发源。**改了 `template/` 之后要重跑**，否则本仓库里的 `./.cowork-flow/run` 跑的还是旧副本。

本仓库自己也走 cowork-flow 流程：`./.cowork-flow/run task next` 给出下一步该做什么，`AGENTS.md` 与 `.cowork-flow/spec/` 是硬约束。

## 测试

```bash
npm run test:fast           # 核心 Node 套件（等价于 npm test）
npm run test:node:full      # 全部 Node 测试
npm run test:integration    # init / sync 关键集成路径
npm run test:template       # 核心模板集成测试
npm run test:template:full  # 完整模板 Python discovery
npm run test:windows:core   # Windows core 发布信心门禁
python -m pytest -q         # 仓库级 Python 测试
npm run release:check       # 全量门禁：node:full + template:full + pack:check
```

`test:fast` 只跑 `package.json` 里列出的核心套件，新增测试文件默认进不了它——按影响面决定要不要加进去。完整分层说明见 [docs/release.md](docs/release.md)。

平台专属用例在缺少前提时会明确跳过。**跳过不得记录为通过**：`release:check` 会原样保留 skip 报告，报告时也要原样说明。

## 提交信息

Conventional Commits，`<type>(<scope>): <中文描述>`：

```
feat(host): 接入 Qoder 宿主（插件形态）
fix(host): 技能声明拆为读取根与宿主发现通道
refactor(zcode): 插件载荷迁到 presets/zcode
```

- `type`：`feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf`
- `scope`：模块名，如 `host`、`cli`、`plugin`、`runtime`、`release`、`tests`、`brand`
- 描述写**做了什么**，不写「优化了体验」这类无信息量的话

## 改宿主适配要动的文件

| 位置 | 内容 |
|---|---|
| `template/.<host>/` | 项目级资产（hook、agents、commands、配置） |
| `template/.cowork-flow/adapters/<host>/adapter.yaml` | 宿主适配声明（技能读取根、发现通道） |
| `template/.cowork-flow/spec/runtime/host-assets.json` | 平台声明、载荷描述符、`obsoleteFiles` |
| `presets/<host>/` | 机器级载荷（插件、预设） |
| `src/commands/install-<host>-*.js`、`src/commands/registry.js` | 安装器与命令面 |
| `test/host-assets.test.js`、`test/host-command.test.js`、`test/<host>-plugin.test.js`、`tests/test_host_*.py` | 对应门禁 |
| `docs/hosts.md` | 宿主接入文档 |

几条硬约束：

- **通用层不写宿主 `if`**。`template/.cowork-flow/scripts/{services,runtime,infra}`、`src/lib/` 的计划与拷贝模块里出现宿主分支，说明分层已经破了——特化只能落在 `spec/runtime/host-assets.json` 的声明、`template/.cowork-flow/scripts/adapters/`、`template/.<host>/` 和显式的宿主 dispatch 模块里。
- **改命令名要一次改全**：`src/commands/registry.js`、doctor 的命令提示、README 命令表、`AGENTS.md`、Skill 正文里的命令引用。README 与注册表的一致性由 `test/cli-registry.test.js` 钉住。
- **不要给宿主不支持的字段塞值**。三份插件清单的图标键集合由 `test/plugin-metadata.test.js` 对照显式支持表校验。
- **不要新增技能分发通道**。技能声明只有读取根与宿主发现通道两条，见 [docs/hosts.md](docs/hosts.md)。

## PR 前置检查

```bash
npm run test:fast        # 至少跑通
npm run release:check    # 触及 template/ presets/ src/commands/ 时跑全量
python -m pytest -q      # 触及 template/.cowork-flow/ 或 tests/ 时
./.cowork-flow/run spec-check      # 改动落在 spec 声明范围内时
```

CI 对 PR 跑两个 job：Ubuntu 上 `release:check` + `pytest`，Windows 上 `test:windows:core` + `pytest`。PR 描述里写清改了哪些文件、验证了哪些命令、有哪些跳过或未验证项。

## 许可

提交即表示同意以 [MIT](LICENSE) 授权。
