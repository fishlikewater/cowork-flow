# Auto install cowork-flow update

## 背景

用户执行 `cowork-flow update` 后，当前 CLI 只提示 `npm install -g cowork-flow@latest`，不会真正执行升级。这与“update 命令”直觉不一致，也让用户必须再手动复制命令。

## 目标

- 当 npm registry 显示存在更新版本时，普通 `cowork-flow update` 自动执行 `npm install -g cowork-flow@latest`。
- 保留 `--global --yes` 兼容路径，不让已有脚本失败。
- 当查询最新版本失败时，继续降级为手动安装提示。

## 范围

- 修改 Node CLI 的 `update` 命令行为、帮助文案和 README 说明。
- 更新 `test/update.test.js` 回归测试。
- 不修改发布脚本、模板同步逻辑或 npm 包名。

## 验收标准

- [ ] `cowork-flow update` 在发现新版本时调用全局安装函数并返回安装退出码。
- [ ] 安装成功时输出 `installed cowork-flow@latest`。
- [ ] npm 查询失败时仍输出当前版本、错误信息和手动安装提示，退出码保持 `0`。
- [ ] `--global --yes` 仍被接受，并触发同一自动安装行为。

## 验证

- `node --test --test-isolation=none test/update.test.js`
- `node --test --test-isolation=none test/cli.test.js`
- `./.cowork-flow/run change validate 05-30-05-30-auto-install-update`
- `./.cowork-flow/run task validate .cowork-flow/tasks/05-30-05-30-auto-install-update`
- `git diff --check`
