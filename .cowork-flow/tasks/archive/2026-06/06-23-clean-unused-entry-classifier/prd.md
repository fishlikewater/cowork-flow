# 清理未接线入口分类器遗留

## 目标

移除当前执行流程不再调用的 `entry_classifier.py` 遗留实现及其模板、校验、测试和文档中的存在性约束，避免下游项目继续安装无效运行时代码。

## 范围

- 删除 root 与 `template/` 中的 `common/entry_classifier.py`。
- 移除 `doctor` 对该文件存在和内容的强制检查。
- 更新初始化、打包、hook 同步测试中对该文件的存在性要求。
- 修正文档中“hook 会调用共享 entry classifier”的过期描述。
- 扫描同类“只被测试/doctor 保护但当前执行路径不调用”的遗留项；仅清理确认不影响当前执行流程的项目。

## 非目标

- 不改变 runtime context 绑定、active task 恢复、contract digest 注入逻辑。
- 不移除 `COWORK_ENTRY_CONTRACT_V1` 合同本身；hook/plugin 仍会注入该合同 digest。
- 不清理与本次无关的既有未提交任务、change、日志或技能文件。

## 验收标准

- AC-001: `entry_classifier.py` 不再随模板安装，也不再被 root/template 同步测试或 doctor 要求存在。
- AC-002: Codex、Claude、OpenCode 当前 hook/plugin 执行路径仍只依赖 runtime context、active task 与 contract registry，相关 focused tests 通过。
- AC-003: 全仓扫描没有遗留的 `entry_classifier.py` 存在性约束或文档声称 hook 调用该 classifier。
- AC-004: 若发现类似遗留项，已证明不在当前执行路径后清理；若未清理，记录理由。

## 预计验证

- `python -m unittest tests.test_codex_hooks tests.test_claude_hooks tests.test_cowork_agents -v`
- `node --test test/init.test.js test/package.test.js`
- `python .cowork-flow/scripts/doctor.py entry-contract`
- `npm run test:all`
