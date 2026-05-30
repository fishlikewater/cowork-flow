## update 命令

### 场景：发现新版本时自动全局安装

- Given 当前安装版本低于 npm registry 最新版本
- When 用户执行 `cowork-flow update`
- Then CLI 应执行 `npm install -g cowork-flow@latest`
- And 安装进程退出码应作为命令退出码返回
- And 安装成功时输出 `installed cowork-flow@latest`

### 场景：兼容旧参数

- Given 当前安装版本低于 npm registry 最新版本
- When 用户执行 `cowork-flow update --global --yes`
- Then CLI 应执行 `npm install -g cowork-flow@latest`
- And 安装进程退出码应作为命令退出码返回

### 场景：npm 查询失败时降级为手动提示

- Given npm 查询最新版本失败
- When 用户执行 `cowork-flow update`
- Then CLI 应输出当前版本
- And CLI 应输出查询错误
- And CLI 应输出手动安装提示 `npm install -g cowork-flow@latest`
- And 命令退出码保持为 `0`
