# 发布与维护

面向 cowork-flow 仓库维护者。用户侧使用见 [README](../README.md)。

## 测试分层

按反馈速度和覆盖范围分层：

```bash
npm run test:fast          # 快速 Node 测试，等价于 npm test
npm run test:integration   # init/sync 关键集成路径
npm run test:node:full     # 完整 Node 测试
npm run test:template      # 核心模板集成测试
npm run test:windows:core  # Windows core 发布信心门禁（Node/Python/init/sync/pack/模板）
npm run test:template:full # 完整模板 Python discovery
npm run test:all           # 发布前全量测试与打包检查
npm run release:check      # 发布信心门禁；当前等价于 test:all
```

Python 侧另有仓库级测试，直接跑 `python -m pytest -q`（`test:template:full` 覆盖的是模板集成部分）。

## 发布

```bash
npm run release          # patch
npm run release -- minor # minor
npm run release -- --version 0.1.0  # 精确发布指定版本（跳过自动 bump）
npm run release -- minor --no-publish  # 完整流程但跳过 npm publish（tag 留在本地）
```

**发布流程：**

1. `npm run release:check`、`git diff --check`
2. 稳定性变更使用 `COWORK_TEMPLATE_TEST_REPEAT=3` 和固定 `COWORK_TEMPLATE_TEST_SEED` 重复运行 `npm run test:template:full`
3. `npm version` 升级版本
4. 同步版本到 `template/.cowork-flow/.version` 和宿主插件清单（`presets/<host>/*-plugin/plugin.json`）
5. `git commit` + `git tag`
6. `npm publish`——走 CI 发布通道时改用 `--no-publish` 在此止步，交由下一步触发

发布说明维护在 `CHANGELOG.md`；发布前更新当前版本段落，并保留 `release:check` 和 `git diff --check` 证据。`scripts/release.sh` 在 bump 前会校验 CHANGELOG 已有该版本段落（`grep -q "^## \[${PACKAGE_VERSION}\] "`），`test/release.test.js` 用假仓库真跑一遍这个门禁。

**CI 发布通道（推荐）：** `scripts/release.sh <release-type> --no-publish` 完成提交与打 tag（不本地 publish）后，先 `git push` 分支并 `git push origin v<v>` 把 tag 推上远端，再 `gh release create v<v>` 触发 `.github/workflows/publish.yml`——远端尚无该 tag 时，`gh release create` 会从默认分支最新提交自动建 tag，使门禁与发布落在错误的提交上。Ubuntu/Windows 双平台全量门禁通过后自动 `npm publish`（需仓库 secret `NPM_TOKEN`，权限：publish）。`--no-publish` 只是跳过最后一步，前置的镜像、门禁与版本同步与默认路径完全一致。

CI 的 PR 同时运行 Ubuntu core 与 Windows core；发布工作流要求 Ubuntu 与 Windows full verification 均成功后才执行 publish。测试 job 不接触 `NPM_TOKEN`，仅 publish job 使用该 secret。

Windows 上发布前使用 `run.cmd` 入口验证；POSIX shell 专属 release 用例在没有 shell 的 Windows 环境会明确跳过，不得记录为通过。`release:check` 会保留这些 skip 报告，不把 skip 伪装成 pass。

## 维护者命令

```bash
npm run source:refresh:dry-run  # 预览本仓库 source checkout live runtime / Skill replica 刷新
npm run source:refresh          # 刷新 ignored root .cowork-flow、.agents/skills、.claude/skills
npm run icons:export            # 从 assets/icon.svg 重导出品牌栅格并同步 codex 载荷副本
```

`source:refresh` 以 `template/.cowork-flow/` 和 `template/skills/` 为唯一 tracked 分发源，刷新 ignored 的根 `.cowork-flow/`、`.agents/skills/`、`.claude/skills/` 受管副本。保护边界：不覆盖 `.cowork-flow/tasks/`、`.cowork-flow/plans/`、`.cowork-flow/.runtime/`、`.cowork-flow/.developer`、`.cowork-flow/config.yaml` 和自定义 Skill。事务语义：复用 Asset Plan / plan applier，失败时回滚；`.cowork-flow/.version` 保持 version-last，并复制 template 版本文件的原始内容。应用后再运行 `./.cowork-flow/run doctor --all --json`。

`icons:export` 需要机器上有 Edge 或 Chrome（无头渲染栅格）；找不到时以非零码退出并打印替代做法，不会静默跳过。`COWORK_FLOW_BROWSER` 可显式指定浏览器可执行文件。
