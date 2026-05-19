# Node CLI 设计：`cowork-flow`

## 背景

当前 `cowork-flow` 是一个模板仓库，核心资产位于 `template/`。使用者需要手动复制模板到目标项目，再按项目事实调整 `AGENTS.md`、`.cowork-flow/config.yaml`、`.cowork-flow/workflow.md` 和 `.cowork-flow/spec/`。

这个流程已经具备清晰的协作闭环，但安装和升级依赖人工复制，容易出现遗漏、路径不一致和版本不可追踪。新增 Node CLI 的目标是把模板分发、CLI 自升级、目标项目模板同步升级纳入统一命令入口，同时保留当前 `.agent/` 与 `.cowork-flow/` 的工作流边界。

## 目标

1. 发布一个 npm CLI 包，包名和命令名均为 `cowork-flow`。
2. 提供 `init` 命令，把仓库内置 `template/` 安装到新项目或已有项目。
3. 提供 `update` 命令，用于升级 CLI 工具本身。
4. 提供 `sync` 命令，用于把已经初始化到目标项目里的 cowork-flow 模板内容同步到当前 CLI 内置版本。
5. 增加 GitHub CI/CD，覆盖 Node CLI 测试、现有 Python 模板测试和 npm 发布流程。
6. 保持模板与 CLI 版本绑定，避免引入远程模板下载或独立模板包的复杂度。

## 非目标

1. 不引入业务代码脚手架。
2. 不让 CLI 取代 `.cowork-flow/scripts/` 中的 Python 工作流脚本。
3. 不在首版实现复杂三方合并、冲突可视化或远程模板版本选择。
4. 不要求 `sync` 自动覆盖用户定制内容。
5. 不拆分独立的模板 npm 包。

## 命令设计

### `cowork-flow init [target]`

把 CLI 包内的 `template/` 复制到目标目录。`target` 省略时使用当前目录。

默认行为：

- 目标目录不存在时创建目录。
- 复制 `AGENTS.md`、`.agent/`、`.cowork-flow/`。
- 不覆盖已存在文件。
- 初始化完成后写入或更新 `.cowork-flow/.version`，记录当前 CLI 包版本。
- 输出下一步建议，例如更新项目名称、技术栈、验证命令和项目规范。

建议参数：

- `--force`：允许覆盖已存在文件。
- `--dry-run`：只展示将创建、跳过或覆盖的文件。

### `cowork-flow update`

升级 CLI 工具本身，而不是目标项目模板。

默认行为：

- 读取当前 CLI 版本。
- 查询 npm 上的 latest 版本。
- 如果当前版本已是最新，输出当前状态。
- 如果存在新版本，输出推荐升级命令。

建议参数：

- `--global`：执行全局安装命令。
- `--yes`：跳过确认，直接执行可执行的升级动作。

首版可以把自动执行升级限定为全局安装场景，避免误判用户使用的是 `npx`、局部 devDependency、pnpm dlx 或其他包管理器入口。

### `cowork-flow sync [target]`

同步目标项目中的 cowork-flow 模板内容。`target` 省略时使用当前目录。

默认行为：

- 检查目标目录是否包含 `.cowork-flow/`。
- 读取 `.cowork-flow/.version` 与当前 CLI 版本。
- 以保护用户改动为默认策略。
- 对明显由模板管理且不应定制的文件执行新增或更新。
- 对常见项目定制文件默认跳过，除非用户传入 `--force`。

首版保护文件：

- `AGENTS.md`
- `.cowork-flow/config.yaml`
- `.cowork-flow/workflow.md`
- `.cowork-flow/spec/**`
- `.cowork-flow/workspace/**`
- `.cowork-flow/tasks/**`
- `.cowork-flow/changes/**`
- `.cowork-flow/plans/**`

首版可安全同步文件：

- `.agent/skills/**`
- `.cowork-flow/scripts/**`
- `.cowork-flow/.gitignore`
- 缺失的模板占位文件，例如 `.gitkeep`

建议参数：

- `--dry-run`：展示同步计划，不写文件。
- `--force`：允许覆盖保护文件。

## 架构

CLI 作为仓库根目录的 Node 项目存在，直接把 `template/` 作为 npm 包内容发布。运行时通过 `import.meta.url` 或等价方式定位包内模板目录，不依赖当前工作目录。

建议文件结构：

```text
.
├── package.json
├── bin/
│   └── cowork-flow.js
├── src/
│   ├── cli.js
│   ├── commands/
│   │   ├── init.js
│   │   ├── sync.js
│   │   └── update.js
│   └── lib/
│       ├── copy-template.js
│       ├── package-info.js
│       └── paths.js
├── test/
│   ├── init.test.js
│   ├── sync.test.js
│   └── update.test.js
└── template/
```

职责边界：

- `bin/cowork-flow.js` 只负责启动 CLI。
- `src/cli.js` 负责参数解析、帮助信息和命令分发。
- `src/commands/*` 负责命令级流程。
- `src/lib/copy-template.js` 负责文件遍历、复制策略、dry-run 结果和覆盖规则。
- `src/lib/package-info.js` 负责读取本地版本、查询 npm latest 和生成升级命令。
- `template/` 继续作为工作流模板唯一来源。

## 技术选型

首版优先使用 Node.js 标准库和 npm 自带测试能力：

- Node.js 20+。
- `node:test` 与 `assert/strict` 编写测试。
- `fs/promises`、`path`、`child_process` 实现文件与命令能力。
- 参数解析可以先使用轻量手写解析，避免为了三个命令引入运行时依赖。

如果后续命令增长，再考虑引入 `commander` 或 `cac`。

## 错误处理

`init`：

- 目标路径无法创建时失败并输出路径。
- 目标存在同名文件且未传 `--force` 时跳过并汇总。
- dry-run 不做任何写入。

`update`：

- 无法访问 npm registry 时，输出当前版本和手动升级命令。
- 自动升级命令失败时透传退出码。

`sync`：

- 目标目录未初始化 cowork-flow 时提示先运行 `cowork-flow init`。
- 保护文件发生冲突时跳过并列出路径。
- `--force` 覆盖前仍输出覆盖列表。

所有命令应使用非零退出码表达失败，方便 CI 和脚本集成。

## CI/CD

新增 GitHub Actions：

`ci.yml`：

- 检出代码。
- 设置 Node.js 20。
- 执行 `npm ci`。
- 执行 Node CLI 测试。
- 执行现有 Python 模板测试：`python3 -m unittest discover tests -v`。

`publish.yml`：

- 在 tag 或手动触发时运行。
- 先执行完整 CI 验证。
- 使用 `NPM_TOKEN` 发布到 npm。
- 发布命令使用 `npm publish`。

`package.json` 建议脚本：

```json
{
  "scripts": {
    "test": "node --test",
    "test:template": "python3 -m unittest discover tests -v",
    "test:all": "npm test && npm run test:template"
  }
}
```

## 测试策略

按 TDD 实现：

1. 先写 `init` 测试，验证模板复制、跳过已有文件、dry-run 和版本写入。
2. 再写 `sync` 测试，验证未初始化报错、保护文件跳过、安全文件同步和 `--force` 覆盖。
3. 再写 `update` 测试，验证当前版本、latest 查询失败降级、生成升级命令。
4. 最后补 CLI 集成测试，验证 `--help`、未知命令和退出码。
5. 保留并运行现有 Python 模板测试，确保 CLI 改造不破坏模板结构。

## 风险与应对

### 用户定制文件被覆盖

默认跳过保护文件，只在 `--force` 下覆盖。`sync` 先输出变更摘要，让用户知道哪些文件会被创建、更新、跳过。

### CLI 自升级场景误判

首版不尝试自动识别所有包管理器。默认只给出升级命令；只有用户明确使用 `--global --yes` 时才执行全局 npm 安装。

### npm 包遗漏模板文件

使用 `package.json` 的 `files` 字段显式包含 `bin/`、`src/`、`template/` 和 `README.md`。CI 增加 npm pack 验证，确认包内包含 `template/AGENTS.md` 与关键脚本。

### Node CLI 与 Python 脚本职责混淆

Node CLI 只负责安装、同步和 CLI 自升级；项目内的任务、change、session 仍由 `.cowork-flow/scripts/` 管理。

## 验收标准

1. `npx cowork-flow init ./demo` 能创建目标目录并复制模板。
2. 重复执行 `init` 不会覆盖已有文件，除非传入 `--force`。
3. `cowork-flow update` 能清楚表达当前版本、最新版本和升级方式。
4. `cowork-flow sync` 能同步安全模板文件，并默认保护项目定制与运行状态。
5. GitHub CI 同时运行 Node CLI 测试和现有 Python 模板测试。
6. npm 发布流程可通过 tag 或手动触发执行，并使用 `NPM_TOKEN` 发布。
