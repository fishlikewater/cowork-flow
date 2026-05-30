# 自动执行 update 升级

## 问题

当前 `cowork-flow update` 在检测到新版本后只输出：

```bash
npm install -g cowork-flow@latest
```

这让用户还需要手动复制执行，和命令名称里的 `update` 预期不一致。

## 目标

- 普通 `cowork-flow update` 在存在新版本时直接执行全局安装。
- 保留旧的 `--global --yes` 参数兼容性。
- npm registry 查询失败时仍给出手动安装提示，避免隐藏可恢复路径。

## 非目标

- 不增加交互确认流程。
- 不改变 `sync`、`init` 或 release 脚本。
- 不改变 npm 包名或安装目标。
