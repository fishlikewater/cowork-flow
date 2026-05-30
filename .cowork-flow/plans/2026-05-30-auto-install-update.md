# 自动执行 update 升级计划

## 假设

- `cowork-flow update` 应表示“执行升级”，不是只打印下一步命令。
- 继续允许 `--global --yes`，但它不再是自动安装的必要条件。
- registry 查询失败时无法判断目标版本，仍应保留手动命令提示。

## 步骤

1. 更新回归测试，覆盖普通 `cowork-flow update` 自动安装、安装退出码透传和旧参数兼容。
   - 验证：`node --test --test-isolation=none test/update.test.js` 在实现前应暴露当前行为差异。

2. 修改 `src/commands/update.js`，在发现新版本时直接调用 `runGlobalInstall('cowork-flow@latest')`。
   - 验证：`node --test --test-isolation=none test/update.test.js`

3. 更新 CLI help 与 README 的升级说明，移除需要手动再执行 npm install 的表述。
   - 验证：`node --test --test-isolation=none test/cli.test.js`

4. 运行变更和任务验证。
   - 验证：`./.cowork-flow/run change validate 05-30-05-30-auto-install-update`
   - 验证：`./.cowork-flow/run task validate .cowork-flow/tasks/05-30-05-30-auto-install-update`
   - 验证：`git diff --check`
