# 修复 Windows update 与 sync 模板刷新

## 背景

在 Windows 环境测试时发现两个问题：

- `cowork-flow update` 无法查询 npm 最新版本，输出降级提示 `Unable to query npm latest. Run: npm install -g cowork-flow@latest`。
- `cowork-flow sync` 无法刷新 `.cowork-flow/scripts/`，且当前 `.cowork-flow` 目录保护范围比期望更宽。

## 目标

- 让 `update` 在 Windows 下可以正常调用 npm 查询最新版本，并在用户显式传入 `--global --yes` 时正常执行全局安装。
- 调整 `sync` 的 `.cowork-flow` 保护规则：只保护 `changes/`、`plans/`、`spec/`、`tasks/`、`workspace/`、`config.yaml`，其他模板文件允许刷新。

## 范围

- 修改 Node CLI 的 update/sync 行为。
- 补充 Node 测试覆盖 Windows npm 调用方式和 sync 保护白名单。
- 不改变 `init` 命令行为。
- 不让 `sync` 删除目标项目中模板不存在的自有文件；本次“替换”仅指模板中存在的同路径文件可被覆盖。

## 成功标准

- Windows 平台 npm 调用不再因为 `npm` shim 执行方式导致查询失败。
- `.cowork-flow/scripts/` 下已有文件会被 `sync` 覆盖为模板版本。
- `.cowork-flow/workflow.md`、`.cowork-flow/agent-team/` 等未列入保护白名单的模板文件会被 `sync` 覆盖。
- `.cowork-flow/config.yaml` 和列入保护白名单的目录内容保持保护。
