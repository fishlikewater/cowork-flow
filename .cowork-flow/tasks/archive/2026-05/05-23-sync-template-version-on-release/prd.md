# Sync template version on release

## Goal

修复 release 脚本只升级 npm 包版本、不同步 `template/.cowork-flow/.version` 的问题。

## Requirements

- release 脚本先运行 `npm run test:all`。
- release 脚本根据 npm 计算出的新版本同步写入 `template/.cowork-flow/.version`。
- release commit/tag 应包含 `package.json`、`package-lock.json`、`template/.cowork-flow/.version`。
- 任一步失败都停止发布。
- 保持 release type 参数校验。

## Acceptance Criteria

- [x] release 测试覆盖 `.version` 同步。
- [x] `node --test test/release.test.js` 通过。
- [x] `./.cowork-flow/run change validate 05-23-sync-template-version-on-release` 通过。

## Technical Notes

- 分级：L1 bugfix。
- Change: `.cowork-flow/changes/05-23-sync-template-version-on-release/`。
- Plan: `.cowork-flow/plans/2026-05-23-sync-template-version-on-release.md`。
