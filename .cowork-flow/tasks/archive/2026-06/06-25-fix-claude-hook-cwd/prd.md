# 修复 Claude hook 非根目录入口

## 目标

Claude Code 的 `UserPromptSubmit` / `SessionStart` hook 即使从非仓库根目录执行，也能稳定启动 cowork-flow 状态注入，不再因为找不到相对路径 `.cowork-flow/run` 报错。

## 范围

- 更新 Claude Code 项目配置中的 hook command。
- 同步 root/template 配置与 doctor 检查。
- 补充能暴露非根 cwd 风险的回归测试。

## 非目标

- 不修改 Python 状态注入逻辑。
- 不新增兼容旧入口或第二套 runner。
- 不改变子代理派发、绑定或 TDD 门禁流程。

## 验收标准

- AC-001: `.claude/settings.json` 与 `template/.claude/settings.json` 的 hook command 不依赖 hook 进程当前目录查找 `.cowork-flow/run`。
- AC-002: `UserPromptSubmit` 与 `SessionStart` 继续使用 cowork-flow runner 启动 `.claude/hooks/inject-workflow-state.py`，不退回裸 `python`。
- AC-003: root/template 的 Claude hook 配置与 doctor 诊断期望保持一致。

## 相关文件

- `.claude/settings.json`
- `template/.claude/settings.json`
- `.cowork-flow/scripts/commands/doctor.py`
- `template/.cowork-flow/scripts/commands/doctor.py`
- `tests/test_claude_hooks.py`
- `tests/test_host_adapters.py`

## 验证方式

- `python -m unittest tests.test_claude_hooks -v`
- `python -m unittest tests.test_host_adapters -v`
- `.\.cowork-flow\run.cmd doctor --host-adapters`
- `git diff --check`
- `npm run test:all`
