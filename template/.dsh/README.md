# DSH Host Adapter 标记

cowork-flow 用本目录识别项目已接入 DeepSeek Harness（DSH），`sync` 据此自动识别并刷新 DSH 资产（`AGENTS.md`、`.agents/skills/`、`.cowork-flow/adapters/dsh/`）。

DSH 侧无需其它配置：`AGENTS.md` 作为工作区指令、`.agents/skills/` 作为技能目录被自动发现。

## DSH 子代理派发与绑定（实测 2026-08-14）

主会话派发正式固定代理（cowork-implement / cowork-check / cowork-research）的实测路径：

1. 主会话创建 runtime context（DSH 无 hook，会话命令需显式设置 `COWORK_FLOW_CONTEXT_ID`）：
   `./.cowork-flow/run subagent init --title <t> --role cowork-implement --execution-task-dir <task-dir> --host dsh --adapter dsh`
   输出 JSON 含 `cowork_runtime_context_id` 与 `cowork_host_context_key`。
2. 用 DSH `subagent` 工具派发子代理，prompt 携带上述两个字段。
3. 子代理首步执行 `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>`；结束后执行 `./.cowork-flow/run subagent close <runtime_context_id>`。

实测结论：bind → status → 读取绑定任务目录 → close 全链路在 DSH 子代理上可用；DSH 子代理具备 shell 工具，绑定状态文件语义正确（close 后 session 文件按设计清理）。

已知局限：bind 生成的 host-session 文件的 `platform` 字段记为 `manual`（运行时 `_platform_from_context_key` 无 `dsh_` 前缀映射）；权威平台字段以 `.cowork-flow/.runtime/subagents/<id>.json` 的 `host: dsh` 为准。映射修复另开任务。

