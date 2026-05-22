# Release 脚本行为规格

## 外部行为

用户在仓库根目录执行：

```bash
npm run release
```

默认等价于发布 patch 版本。用户也可以执行：

```bash
npm run release -- minor
npm run release -- major
npm run release -- prerelease
```

脚本必须按顺序执行：

1. `npm run test:all`
2. `npm version <release-type>`
3. `npm publish`

其中 `<release-type>` 默认为 `patch`，也可以是 npm 支持的语义化版本升级类型：
`major`、`minor`、`patch`、`premajor`、`preminor`、`prepatch`、`prerelease`。

## 错误行为

- 如果传入不支持的版本升级类型，脚本返回非零退出码，并输出允许的类型。
- 如果 `npm run test:all` 失败，脚本不得执行 `npm version` 或 `npm publish`。
- 如果 `npm version <release-type>` 失败，脚本不得执行 `npm publish`。
- 如果 `npm publish` 失败，脚本返回 npm publish 的失败状态。

## 文档行为

README 的“发布流程”必须说明：

- 推荐使用 `npm run release` 发布。
- 默认升级 patch 版本。
- 如何传入 `minor`、`major`、`prerelease`。
- 脚本会先跑完整验证，再升级版本并发布。
- 需要 npm 登录或 `NPM_TOKEN` 等 npm 发布凭据。

## 验收标准

- [ ] release 脚本默认使用 patch。
- [ ] release 脚本支持显式版本类型。
- [ ] release 脚本在失败时停止后续步骤。
- [ ] `package.json` 暴露 `release` npm script。
- [ ] `package-lock.json` 根包版本与 `package.json` 一致。
- [ ] README 发布说明与脚本行为一致。
- [ ] `npm run test:all` 通过。
