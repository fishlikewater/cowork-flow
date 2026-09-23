# 安全策略

## 支持的版本

只维护最新的 minor 版本（当前 `1.x`）。安全修复进入下一个 patch 版本，不回补旧 minor。历史版本的内容见 [CHANGELOG.md](CHANGELOG.md)。

## 上报漏洞

用 GitHub 的私密漏洞上报：仓库 **Security → Advisories → Report a vulnerability**（<https://github.com/fishlikewater/cowork-flow/security/advisories/new>）。不要开公开 issue。

请在报告里说明：受影响的命令与版本、复现步骤、你观察到的实际影响。这是一个无商业支持的业余项目，没有响应时限承诺；能确认的问题会在下一个 patch 版本修掉并在 CHANGELOG 记录。

## 这个项目的攻击面

cowork-flow 是一个零运行时依赖的 CLI。它自己不发起网络请求，唯一的例外是 `cwf self update`——它驱动 npm 访问 registry 并全局安装包。它不收集遥测，但它会**以你的身份写文件、并让宿主执行脚本**。值得报的问题集中在这几类：

| 面 | 相关命令 | 典型问题 |
|---|---|---|
| 写入目标项目 | `cwf project init` / `cwf project sync` | 路径穿越、写到目标目录之外、覆盖它声明会保护的文件（`config.yaml`、`.developer`、`spec/`、任务与计划） |
| 写入宿主配置目录 | `cwf host add` / `cwf host remove` | 写到宿主目录之外、破坏宿主自己的配置、卸载时删掉不属于 cowork-flow 的条目 |
| 转发给宿主 CLI | `cwf host add codex` 等 | 参数/路径拼进宿主命令时被当成额外选项执行 |
| 宿主 hook 与注入脚本 | 各宿主的 `PostToolUse` hook | 把工具输入（文件路径、工具输出、任务事实）当成指令执行，而不是当成数据 |
| 事实层 | `cwf mcp serve` / `./.cowork-flow/run mcp-state` | 把项目事实暴露给不该看到它的进程 |
| 技能脚本 | `./.cowork-flow/run <命令>` | 项目内的运行时脚本被非预期输入触发危险操作 |
| 自升级 | `cwf self update` | 从 registry 拉到非预期版本并全局安装；供应链与版本固定问题 |

## 不在范围内

- 宿主产品本身的漏洞（Codex、Claude Code、OpenCode、ZCode、Qoder、Kimi Code、DeepSeek Harness）——请报给对应厂商。
- 需要攻击者已经能在你的机器上执行代码才能触发的问题。
- 你把 `cwf project sync --force` 用在了自己不想被覆盖的目录上（`--force` 的语义就是整文件覆盖保护文件）。
- 未固定的 `npx cowork-flow` 拉到的版本与仓库默认分支 `dev` 之间的差异。
