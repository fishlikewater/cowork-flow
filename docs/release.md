# 发布与维护

本文面向 cowork-flow 仓库维护者。普通用户只需要 [README](../README.md)；提交代码前先看 [贡献指南](../CONTRIBUTING.md)。

## 发布前检查

按改动范围选择测试，不必每次都从最重的命令开始。

| 命令 | 什么时候运行 |
|---|---|
| `npm run test:fast` | 日常修改后的最低检查 |
| `npm run test:smoke` | 验证 CLI 可加载，并从真实 npm tarball 安装后运行最小初始化 |
| `npm run test:integration` | 改动 `project init` / `project sync` |
| `npm run test:node:full` | 改动 Node CLI、安装器或共享模块 |
| `npm run test:template` | 改动项目模板的核心路径 |
| `npm run test:template:full` | 改动 Python 运行时、规范、hook 或宿主适配 |
| `npm run test:windows:core` | 涉及 Windows、路径、换行或发布行为 |
| `python -m pytest -q` | 改动 `template/.cowork-flow/`、`tests/` 或 Python 契约 |
| `npm run test:all` | 准备发布时的完整 Node、模板和打包检查 |
| `npm run release:check` | 发布信心门禁，当前等价于 `test:all` |

平台前提不满足时，测试可能明确跳过。跳过项必须原样记录，不能当作通过。

稳定性相关改动建议重复运行模板测试：

```bash
COWORK_TEMPLATE_TEST_REPEAT=3 \
COWORK_TEMPLATE_TEST_SEED=<固定值> \
npm run test:template:full
```

## 发布命令

| 命令 | 行为 |
|---|---|
| `npm run release` | 发布 patch 版本 |
| `npm run release -- minor` | 发布 minor 版本 |
| `npm run release -- --version 0.1.0` | 使用指定版本号，跳过自动 bump |
| `npm run release -- minor --no-publish` | 完成版本、提交和 tag，推送 commit 与 tag，但不执行 `npm publish`；由 CI 发布 |
| `npm run release -- --dry-run` | 运行发布前检查，停在版本 bump 之前 |

`--dry-run` 不是只读命令。它会先要求 Git 工作树和暂存区干净，再执行 `source:refresh` 和 `sync --force`，因此可能刷新仓库中被忽略的运行副本，并临时覆盖后恢复 `AGENTS.md`。它不会改版本文件、提交、打 tag 或发布；如果检查开始时已有本地修改，脚本会在任何刷新前停止。

目标版本只有 bump 后才能确定，所以 `--dry-run` 不会运行 CHANGELOG 版本段落门禁。

## 标准发布流程

1. 确认工作树和更新日志符合预期。
2. 运行 `npm run release:check` 和 `git diff --check`。
3. 稳定性改动按上一节重复模板测试。
4. 运行 `npm run release -- <release-type>`；CI 通道使用 `--no-publish`，它会把 tag 推给 CI。
5. 脚本同步 `package.json`、lockfile、`template/.cowork-flow/.version` 和所有随包插件清单。
6. 检查提交与 tag，再按下面的 CI 通道发布。

`scripts/release.sh` 会在 bump 后检查 `CHANGELOG.md` 是否存在当前版本段落。这个检查发生在版本已经修改之后；如果失败，按脚本输出的撤销命令恢复 `package.json`、`package-lock.json`、`.version`，再运行 `npm run source:refresh`。

## CI 发布通道

推荐让 GitHub Actions 执行 `npm publish`：

1. 在本地运行 `npm run release -- <release-type> --no-publish`。脚本完成检查、版本、提交和 tag，然后推送分支与 tag：

   ```bash
   git push
   git push origin v<v>
   ```

2. 推送 tag 即触发 `.github/workflows/publish.yml`。工作流等待 Ubuntu 和 Windows 验证通过后，只从已存在的 `v<version>` tag 发布，并核对 tag、`package.json` 与 `template/.cowork-flow/.version` 的版本一致。

3. 需要给这个 tag 写 Release 说明时，再手动创建（不是发布的必要步骤）：

   ```bash
   gh release create v<v>
   ```

不要在 tag 尚未存在于远端时运行 `gh release create`，否则 GitHub 可能从默认分支最新提交创建 tag，把发布指向错误提交。

同一 tag 的重复触发会被 concurrency 锁串行化，不会并发抢发；如果该版本已经发到 npm，重复运行会在 `npm publish` 阶段被 npm 拒绝，这是预期行为。上一次 CI 失败需要重发时，用 `workflow_dispatch` 指定同一个 tag 重跑即可。

PR 和发布使用同一套 core 门禁。

发布凭据走 **Trusted Publishing**：publish job 声明 `id-token: write`，把 GitHub OIDC token 交给 npm 换取短期凭据，仓库里不保存长期 token。登记在 npm 包页面（Settings → Trusted Publishers），声明仓库 `fishlikewater/cowork-flow` 与 workflow 文件 `publish.yml`。

该交换由 npm CLI 实现（11.5.1 起），而 Node 20 自带 npm 10，因此**只有 publish job 跑在 Node 24**；两个验证 job 仍用 Node 20，与 `package.json` 声明的 `engines` 保持一致。

publish job 的 `setup-node` **保留 `registry-url`**，但不提供 `NODE_AUTH_TOKEN`。npm 需要在 `.npmrc` 里读到 registry 才会发起 OIDC 交换——去掉它，发布会在未接触令牌端点的情况下直接以 `ENEEDAUTH` 失败。`setup-node` 写入的 `${NODE_AUTH_TOKEN}` 占位符则**故意不解析**：npm 会带着这个空凭据先尝试交换，只有交换被拒时才回退到它。

早期版本用 `NPM_TOKEN` secret。若账号开启双因素认证，classic token 无法完成交互式 OTP，CI 发布会以 `EOTP` 失败——这也是改用 Trusted Publishing 的原因。验证 job（Ubuntu / Windows）不接触任何发布凭据，只跑 `release:check`。

## 维护者命令

```bash
npm run source:refresh:dry-run  # 预览源码仓库运行副本的刷新
npm run source:refresh          # 刷新根 .cowork-flow、.agents/skills、.claude/skills
npm run icons:export            # 从 assets/icon.svg 重新导出 PNG
```

`source:refresh` 以 `template/.cowork-flow/` 和 `template/skills/` 为唯一分发源，不覆盖任务、计划、开发者身份、项目配置或自定义 Skill。刷新后运行：

```bash
./.cowork-flow/run doctor --all --json
```

`icons:export` 需要本机存在 Edge 或 Chrome，可用 `COWORK_FLOW_BROWSER` 指定可执行文件。浏览器缺失时命令会失败，不会把旧图当作已更新。
