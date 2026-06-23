# 统一规则规范和整理 spec 目录 Proposal

## 背景

当前 workflow gate 的规则定义和执行逻辑分散在多个位置：`rules.json` 保存部分规则元数据，`validate_implementation.py` 又硬编码了 R-AG-002 等禁止规则的 message/fix_hint，`registry.json` 被宿主插件读取但缺失时会降级，`spec/` 根目录同时放人读合同、机器 schema、runtime 配置和领域规范。

这种结构会导致：

- 同一条规则多处维护，修改时容易不同步。
- 缺失规则/注册文件时约束静默变弱。
- `source_line` 这类元数据随文档行号变化而腐化。
- downstream template 用户难以判断哪些 spec 文件是人读规范，哪些是 runtime 输入。

## 目标

- 规则元数据单源化。
- `spec/` 目录按用途分层。
- 缺失关键规则/合同文件可检测、可解释。
- 保持 root/template 分发一致。

## 用户价值

让 cowork-flow 从“能跑的一组脚本”进一步变成可维护、可交付的产品化工作流：规则可审计、路径可理解、模板可验证，AI 执行流程不依赖隐式硬编码。

## 范围

- 迁移并整理 `.cowork-flow/spec/`。
- 更新规则加载和 implementation gate。
- 更新 TDD evidence/test intent 的格式校验。
- 更新测试和打包检查。

## 范围边界

- 只整理 cowork-flow 自身的规范、合同、schema 和 runtime 规则入口。
- 不重写 core CLI 或宿主 adapter 的执行模型。
- 不删除历史 archive，不迁移旧归档中的旧路径文本。
- 不引入新规则语言或通用 DSL。

## 风险

- 路径迁移影响 hooks/plugins/doctor/tests/package。
- 规则文件缺失从静默通过改成显式失败，可能暴露旧测试 fixture 不完整。
- 历史 archive 保留旧路径，不迁移历史记录。
