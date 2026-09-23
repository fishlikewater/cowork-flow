## 改了什么

<!-- 一句话说清改动，再列关键文件。 -->

## 为什么

<!-- 关联的 issue 或任务目录（.cowork-flow/tasks/<id>）。 -->

## 验证

- [ ] `npm run test:fast`
- [ ] `npm run release:check`（触及 `template/`、`presets/`、`src/commands/` 时）
- [ ] `python -m pytest -q`（触及 `template/.cowork-flow/` 或 `tests/` 时）
- [ ] `./.cowork-flow/run spec-check`（改动落在 spec 声明范围内时）

<!-- 贴原始结果，写明 skip 数与未执行项。平台 skip 不得记作通过。 -->

## 自检

- [ ] 没有引入运行时依赖（`dependencies` / `devDependencies` 仍为空）
- [ ] 没有给宿主写它 schema 不支持的字段
- [ ] 改命令名时同步了 `src/commands/registry.js`、doctor 的命令提示、README 命令表、`AGENTS.md` 与技能正文
- [ ] 改了文档时 `docs/` 与 README 的相对链接仍然有效（`test/docs.test.js` 会校验）
- [ ] 本 PR 不含与本改动无关的重构或格式化

参考 [CONTRIBUTING.md](../CONTRIBUTING.md) 与 [docs/architecture.md](../docs/architecture.md)。
