# 日期前缀 slug 幂等处理计划

## 假设

- `MM-DD-` 形式的任意日期前缀都应视为已带前缀，不只识别当天日期。
- `task.json` 中的 `id` / `name` 继续保留用户传入的 slug 原值；本次只改变目录名去重。
- root 和 `template/` 脚本必须镜像修改。

## 步骤

1. 为 `change create` 和 `task create` 增加回归测试，覆盖已带日期前缀时不重复添加。
   - 验证：相关测试在实现前应失败。

2. 在 common paths 中新增共享 helper，并让 `task.py` / `change.py` 使用该 helper。
   - 验证：`node scripts/run-template-tests.js`

3. 将 root `.cowork-flow/scripts/` 与 `template/.cowork-flow/scripts/` 同步修改。
   - 验证：`npm run test:all`

4. 运行工作流校验。
   - 验证：`./.cowork-flow/run change validate 05-30-date-prefix-idempotent`
   - 验证：`./.cowork-flow/run task validate .cowork-flow/tasks/05-30-date-prefix-idempotent`
   - 验证：`git diff --check`
