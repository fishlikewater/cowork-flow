# 行为规格

## update 命令

### 场景：Windows 下查询 npm 最新版本

- Given 当前运行平台是 Windows
- And 用户执行 `cowork-flow update`
- When CLI 调用 npm 查询 `cowork-flow` 最新版本
- Then 应使用 Windows 可执行 npm shim 的调用方式
- And 查询成功时输出 `current=<version>` 与 `latest=<version>`
- And 不应因为 npm shim 启动失败而进入 `Unable to query npm latest` 降级分支

### 场景：Windows 下执行全局更新

- Given 当前运行平台是 Windows
- And 用户执行 `cowork-flow update --global --yes`
- And npm registry 显示存在更新版本
- When CLI 执行全局安装
- Then 应使用 Windows 可执行 npm shim 的调用方式运行 `npm install -g cowork-flow@latest`
- And 安装进程退出码应作为命令退出码返回

### 场景：npm 查询确实失败

- Given npm 查询命令返回错误
- When 用户执行 `cowork-flow update`
- Then CLI 继续输出当前版本
- And 输出手动安装提示 `npm install -g cowork-flow@latest`
- And 命令退出码保持为 `0`

## sync 命令

### 场景：刷新 `.cowork-flow` 非保护模板文件

- Given 目标项目已经初始化
- And 目标项目存在旧版本 `.cowork-flow/scripts/*.py`
- When 用户执行 `cowork-flow sync <target>`
- Then `.cowork-flow/scripts/*.py` 应被模板版本覆盖

### 场景：只保护指定 `.cowork-flow` 路径

- Given 目标项目已经初始化
- And 目标项目存在自定义 `.cowork-flow/config.yaml`
- And 目标项目存在自定义 `.cowork-flow/spec/`、`.cowork-flow/changes/`、`.cowork-flow/plans/`、`.cowork-flow/tasks/`、`.cowork-flow/workspace/` 内容
- When 用户执行 `cowork-flow sync <target>`
- Then 上述文件和目录内容应保持保护，不被模板覆盖
- And `.cowork-flow/workflow.md`、`.cowork-flow/agent-team/`、`.cowork-flow/run`、`.cowork-flow/run.cmd` 等未列入保护白名单的模板文件应被模板版本覆盖

### 场景：保留目标项目独有文件

- Given 目标项目存在模板中没有的自有文件
- When 用户执行 `cowork-flow sync <target>`
- Then sync 不应删除该自有文件
