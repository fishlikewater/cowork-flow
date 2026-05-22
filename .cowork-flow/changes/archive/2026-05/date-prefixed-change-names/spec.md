# Change 目录命名规格

## 新建 change

- Given 用户在项目中执行 `./.cowork-flow/run change create replace-auth`
- When 命令成功
- Then 系统 MUST 在 `.cowork-flow/changes/` 下创建 `MM-DD-replace-auth` 目录，其中 `MM-DD` 使用本地当前日期，格式与 task 目录前缀一致。
- And 命令输出 MUST 包含实际创建的目录名。
- And `change.yaml` 中的 `slug` MUST 等于实际目录名，保证 `change validate <目录名>` 可以直接通过目录名校验。

## 兼容性

- Existing 裸 slug change 目录 MUST continue to be validated, listed, and archived by their existing directory names.
- The change archive layout remains `.cowork-flow/changes/archive/YYYY-MM/<change-dir>` and MUST NOT gain an additional date layer.
- Invalid slug input validation remains based on the user-provided slug before prefixing.

## 验收标准

- Regression tests cover `change create` producing a date-prefixed directory.
- Existing change validation/archive/list tests still pass.
- Template script and current project script remain aligned for this behavior.
