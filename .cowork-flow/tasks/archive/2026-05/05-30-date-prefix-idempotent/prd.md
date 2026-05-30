# Make date-prefixed slugs idempotent

## 背景

`task create` 和 `change create` 会自动在 slug 前添加当天 `MM-DD` 前缀。如果调用方传入的 slug 已经带有日期前缀，当前实现会生成 `05-30-05-30-...` 这类重复目录名。

## 目标

- 当 slug 已经以 `MM-DD-` 开头时，`task create` 和 `change create` 不再重复添加日期前缀。
- 当 slug 没有日期前缀时，继续自动添加当天日期前缀。
- root 与 `template/` 中的工作流脚本保持一致。

## 范围

- 修改 `.cowork-flow/scripts/common/paths.py` 及 template 镜像。
- 修改 `.cowork-flow/scripts/task.py`、`.cowork-flow/scripts/change.py` 及 template 镜像。
- 更新 Python 回归测试。
- 不改变已有任务或 change 的归档/校验规则。

## 验收标准

- [ ] `task create --slug demo` 生成 `MM-DD-demo`。
- [ ] `task create --slug MM-DD-demo` 生成 `MM-DD-demo`，不重复前缀。
- [ ] `change create demo` 生成 `MM-DD-demo`。
- [ ] `change create MM-DD-demo` 生成 `MM-DD-demo`，不重复前缀。
- [ ] root/template 镜像脚本一致。

## 验证

- `node scripts/run-template-tests.js`
- `npm run test:all`
- `./.cowork-flow/run change validate 05-30-date-prefix-idempotent`
- `./.cowork-flow/run task validate .cowork-flow/tasks/05-30-date-prefix-idempotent`
- `git diff --check`
