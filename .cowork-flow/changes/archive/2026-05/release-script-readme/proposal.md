# 添加 npm release 脚本并更新 README

## 背景

当前发布 npm 包时需要人工修改 `package.json` 版本号。最近一次提交已经出现
`package.json` 为 `0.0.5`、`package-lock.json` 根包仍为 `0.0.4` 的不一致，
说明手动升级版本容易遗漏锁文件，发布链路存在可避免风险。

## 目标

- 增加一个 npm release 脚本，默认执行 patch 版本升级。
- 支持显式传入 `minor`、`major`、`prerelease` 等 npm 支持的版本升级类型。
- 发布前运行项目完整验证，避免未经验证的包被发布。
- 通过 `npm version` 同步更新 `package.json` 和 `package-lock.json`，减少人工改版本。
- 更新 README，说明新的发布命令和注意事项。

## 非目标

- 不重写 GitHub Actions 发布工作流。
- 不引入 changelog 生成、GitHub Release 创建或多包 monorepo 发布能力。
- 不绕过 npm 自身的版本校验、认证和发布失败处理。
