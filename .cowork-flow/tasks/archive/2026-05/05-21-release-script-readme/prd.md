# 添加 npm release 脚本并更新 README

## Goal

让维护者发布 npm 包时不再手动修改版本号，通过 shell 发版脚本完成发布前验证、版本升级和 npm publish。

## Requirements

- 新增 `scripts/release.sh`，默认执行 patch 版本升级。
- 支持显式传入 `major`、`minor`、`patch`、`premajor`、`preminor`、`prepatch`、`prerelease`。
- 发布命令顺序固定为：完整验证、`npm version <type>`、`npm publish`。
- 任一步骤失败时停止后续步骤。
- `package.json` 暴露 `release` npm script。
- 修复当前 `package-lock.json` 根包版本与 `package.json` 不一致的问题。
- README 说明新发布命令、默认行为和凭据要求。

## Acceptance Criteria

- [ ] `npm test -- test/release.test.js` 覆盖默认 patch、显式版本类型、非法类型和失败短路。
- [ ] `npm test -- test/package.test.js` 验证 release script 存在、lockfile 根版本一致。
- [ ] README 发布流程包含 `npm run release` 及常用版本类型示例。
- [ ] `npm run test:all` 通过。

## Technical Notes

- 使用 POSIX shell 脚本，不新增第三方依赖。
- 使用 npm 原生命令 `npm version` 同步 package 元数据，不手写语义化版本计算。
- 本次不改 GitHub Actions 发布 workflow。
