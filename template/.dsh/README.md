# DSH Host Adapter 标记

cowork-flow 用本目录识别项目已接入 DeepSeek Harness（DSH），`sync` 据此自动识别并刷新 DSH 资产（`AGENTS.md`、`.agents/skills/`、`.cowork-flow/adapters/dsh/`）。

DSH 侧无需其它配置：`AGENTS.md` 作为工作区指令、`.agents/skills/` 作为技能目录被自动发现。

## DSH 子代理派发与绑定（实测 2026-08-14）

主会话派发正式固定代理（cowork-implement / cowork-check / cowork-research）的实测路径：

1. 主会话创建 runtime context（未安装 workflow-state hook 时，会话命令需显式设置 `COWORK_FLOW_CONTEXT_ID`）：
   `./.cowork-flow/run subagent init --title <t> --role cowork-implement --execution-task-dir <task-dir> --host dsh --adapter dsh`
   输出 JSON 含 `cowork_runtime_context_id` 与 `cowork_host_context_key`。
2. 用 DSH `subagent` 工具派发子代理，prompt 携带上述两个字段。
3. 子代理首步执行 `./.cowork-flow/run subagent bind <runtime_context_id> <host_context_key>`；结束后执行 `./.cowork-flow/run subagent close <runtime_context_id>`。

实测结论：bind → status → 读取绑定任务目录 → close 全链路在 DSH 子代理上可用；DSH 子代理具备 shell 工具，绑定状态文件语义正确（close 后 session 文件按设计清理）。

已知局限：bind 生成的 host-session 文件的 `platform` 字段记为 `manual`（运行时 `_platform_from_context_key` 无 `dsh_` 前缀映射）；权威平台字段以 `.cowork-flow/.runtime/subagents/<id>.json` 的 `host: dsh` 为准。映射修复另开任务。

## workflow-state hook（可选，机器级）

`init` / `sync` 只交付项目资产；实时 `<workflow-state>` 注入是可选的机器级安装，不需要切换 DSH preset：

```bash
cowork-flow install-dsh-hook              # 安装到 $DSH_HOME/cordis.patch.yml（默认 ~/.dsh）
cowork-flow install-dsh-hook --dry-run    # 预览，不写文件
cowork-flow install-dsh-hook --uninstall  # 卸载；--force 同时删除插件文件
```

- 注册后对 DSH **所有** preset / 会话生效；systemPrompt 尾部注入 `<workflow-state>` 块，每条用户消息刷新，`task` / `subagent` / `resume` 命令落定后轮内刷新。`cordis.patch.yml` 在启动时组合：安装或更新后需**重启 DSH** 才生效。
- 无 `.cowork-flow` 根的项目零开销跳过：插件 JS 预检短路，不注入内容、不启动 Python。
- 全局开关（环境变量）：`COWORK_FLOW_HOOKS=0` / `COWORK_FLOW_DISABLE_HOOKS=1`。
- 与 `install-dsh-preset` 二选一：预设已内置同一 hook，同时安装可能造成重复注入。

