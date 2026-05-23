# 发布时同步模板版本文件

## 背景

`scripts/release.sh` 当前执行 `npm version <type>` 和 `npm publish`。`npm version` 会更新 `package.json` 与 `package-lock.json`，但不会更新项目模板里的 `template/.cowork-flow/.version`。这会导致发布后的 npm 包版本与模板自带版本文件不一致。

## 目标

发布脚本在升级 npm 包版本时同步更新 `template/.cowork-flow/.version`，并确保 release commit/tag 包含该文件。

## 范围

- 修改 `scripts/release.sh`。
- 更新 release 脚本测试。
- 必要时更新 README 中发布流程说明。

## 非目标

- 不改变 npm 支持的 release type 列表。
- 不引入新的发布工具。
- 不执行真实 npm publish。
