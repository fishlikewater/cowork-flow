# MCP 客户端接入指南

把 cowork-flow 事实层接入任意 MCP 客户端。两种入口：

- **全局（推荐）**：`cowork-flow mcp-state`（npm 全局 CLI 透传，`npm i -g cowork-flow@>=1.1.0`）。注册一次，所有 cowork-flow 项目通用——root 由客户端启动时的 cwd 向上解析（与 server 内部语义一致）。
- **项目级**：`<project>/.cowork-flow/run mcp-state`（不依赖全局安装，但每项目一份配置）。

以下配置均为 stdio 注册（`command` + `args`），工具为 `task_state` / `task_list`。

## Codex（`~/.codex/config.toml`）

```toml
[mcp_servers.cowork-flow]
command = "cowork-flow"
args = ["mcp-state"]
```

项目级等价：`command = "/absolute/path/to/project/.cowork-flow/run"`、`args = ["mcp-state"]`。

## OpenCode（`~/.config/opencode/opencode.json`）

```json
{
  "mcp": {
    "cowork-flow": {
      "type": "local",
      "command": ["cowork-flow", "mcp-state"],
      "enabled": true
    }
  }
}
```

OpenCode 另有 `shell.env` 注入 `COWORK_FLOW_CONTEXT_ID`，会话绑定与 MCP 查询共享同一会话身份。

## Claude Code（项目级 `.mcp.json` 或 `claude mcp add`）

```json
{
  "mcpServers": {
    "cowork-flow": {
      "command": "cowork-flow",
      "args": ["mcp-state"]
    }
  }
}
```

命令行等价：`claude mcp add -s user cowork-flow -- cowork-flow mcp-state`。

## ZCode

在 ZCode 客户端设置的 MCP 服务器中添加同构条目（stdio）：命令 `cowork-flow`、参数 `mcp-state`。ZCode 的 hook 注入（`<workflow-state>`）与 MCP 查询并行工作：注入负责写入时机，MCP 负责按需查询。

## 验证

最小会话自检（任何注册方式都等价于这一条管道）：

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | cowork-flow mcp-state
```

预期两行 JSON-RPC 响应（serverInfo `cowork-flow-facts`；工具 `task_state` / `task_list`）。自动化等效验证见 `test/mcp-client-matrix.test.js`（全局命令、项目级 runner、嵌套子目录三种启动形态）。

修改客户端配置后需重启该客户端会话生效。
