# 架构与扩展点

本文说明 cowork-flow 自身的仓库布局、运行时分层，以及规范挂命令（spec-check）机制。用户侧怎么用见 [README](../README.md)；宿主接入细节见 [hosts.md](hosts.md)。

## 交付树与仓库自身

`template/` 是**唯一 tracked 分发源**：`cwf project init` / `cwf project sync` 把它的内容按平台拷进目标项目。

```
template/
├── AGENTS.md                  # 协作入口（编码原则、流程约定）
├── CLAUDE.md                  # Claude Code 入口
├── skills/                    # ⭐ 唯一源码，init 时按平台分发
├── .codex/                    # Codex agents / hooks / config
├── .claude/                   # Claude Code settings / agents / hooks
├── .opencode/                 # OpenCode agents / commands / plugins
├── .dsh/                      # DeepSeek Harness 标记（sync 检测 + 说明）
├── .kimi-code/                # Kimi Code fixed agents（cowork-implement / check / research）
└── .cowork-flow/
    ├── config.yaml            # 项目配置
    ├── scripts/               # Python 运行时
    ├── spec/                  # 规范文档（contracts / schemas / guides）
    ├── plans/                 # 实现计划
    └── tasks/                 # 任务目录

presets/                       # ⭐ 机器级插件载荷：安装器拷进宿主配置目录，不落项目
├── zcode/                     # ZCode 插件（hooks + agents + .zcode-plugin/plugin.json）
├── qoder/                     # Qoder 插件（hooks + agents + .qoder-plugin/plugin.json）
├── codex/                     # Codex 插件（.codex-plugin/plugin.json + assets + 引导技能；agents/hook 留在项目级）
├── opencode/                  # OpenCode 插件（plugins/cowork-flow.js + cowork-flow/：逻辑模块与引导技能；hook/agents 留在项目级）
├── claude-code/               # Claude Code skills 目录插件（.claude-plugin/plugin.json + 引导技能；hook/agents 留在项目级）
├── kimi-code/                 # Kimi Code hook shim
└── dsh/                       # DSH agent 预设
```

仓库自身的目录（不参与分发）：

```
assets/                        # 品牌资产：icon.svg 唯一源 + 导出的 icon.png
src/                           # 分发层（Node CLI）：commands/ 子命令 + lib/ 计划与模板拷贝
scripts/                       # 构建与发布：pack-check、release、模板测试运行器、品牌重导出
test/                          # Node 测试（node --test 收集本目录所有 .js），*.test.js 为主
tests/                         # Python 测试（pytest / unittest），test_*.py + fixtures/
docs/                          # 架构 / 宿主 / 发布三类文档
.agents/ .claude/ .codex/ .cowork-flow/   # 源 checkout 的活实例（gitignored，由 npm run source:refresh 维护）
```

测试按语言分目录：`test/` 归 Node，`tests/` 归 Python。`node --test` 会收集 `test/` 下**所有** `.js`（不限 `*.test.js`，`test/helpers/` 里的辅助模块同样会被加载）；Python 侧按各自默认模式收集——pytest 收 `test_*.py` / `*_test.py`，unittest `discover` 收 `test*.py`。放在这些目录里的辅助文件必须保持无副作用。

字节码隔离：`tests/__init__.py`（pytest 与 unittest 都会先导入的包）把 Python 字节码前缀指到 gitignored 的 `.tmp/pycache`——本进程设 `sys.pycache_prefix`，并通过 `PYTHONPYCACHEPREFIX` 传给子进程；Node 测试由 `test/helpers/bytecode-isolation.js` 做同一件事。技能脚本的子进程走另一条规则：`runtime_pythonpath_env(cache_bytecode=False)` 关掉字节码写入，`run.py` 与批处理入口（`batch_mode.py`）共用这一条——技能脚本低频、缓存收益可忽略，而它留下的 `__pycache__` 会落在脚本解析到的 runtime（源 checkout 里就是交付树）。`tests/test_no_legacy_template_paths.py` 有门禁断言钉住 `template/`、`presets/` 的零字节码状态。

## 运行时分层

运行时代码全部在 `template/.cowork-flow/scripts/` 下（下面省略该前缀，仓库根的 `scripts/` 只有发布与构建脚本）：

- **服务层**：任务创建、生命周期、归档、上下文、任务树和 runtime context 编排位于 `scripts/services/`；命令层只负责参数和输出适配。
- **状态存储层**：`scripts/infra/storage/` 提供显式 UTF-8、修订检查、操作日志和可恢复 Unit of Work；任务与会话写入不再直接散落在命令函数中。
- **Host Asset Manifest**：`spec/runtime/host-assets.json` 是宿主资产、平台识别、同步策略和 obsolete 迁移清单的权威来源。新增平台或资产时更新 Manifest 与 schema，不在 CLI 中新增硬编码集合。
- **事务式 init/sync**：CLI 先构建不可变 Asset Plan，在同文件系统 staging 中校验 hash/权限，再按备份清单提交；失败时逆序回滚，`.cowork-flow/.version` 最后更新。
- **共享 Hook 核心**：Codex 与 Claude Code Hook 只做宿主输入适配，工作流状态解析由 `scripts/adapters/host/workflow_state_hook.py` 统一实现。
- **流程内核**：公开任务入口只有 `task next`；kernel 只解析状态事实和 action，Skill 所有权由 manifest loader 注入，硬门禁由 runtime gate 执行，不再分发独立流程中枢文件或 Skill 注册控制面。
- **Skill 自带脚本**：只服务单个 Skill 的控制器或辅助脚本放在 `template/skills/<skill-id>/scripts/`，由 `.cowork-flow/run` 薄分发；`scripts/` 内核只保留任务导航、生命周期、gate、host/runtime、存储和分发所需代码。

平台特化只允许落在四类位置：`spec/runtime/host-assets.json` 的声明、`scripts/adapters/`、`template/.<host>/`、以及显式的宿主 dispatch 模块（`src/commands/install-<host>-*.js` 与 `src/lib/plugin-metadata.js` 里的清单投影表）。通用层——`scripts/services|runtime|infra`、`src/lib/` 的计划与拷贝模块（`asset-plan.js`、`copy-template.js`、`plan-applier.js`）——出现宿主分支就说明分层已经破了。

## 规范挂命令（spec-check）

`.cowork-flow/spec/` 下的规范可在文件首部 frontmatter 声明检查命令；机制只执行声明、不解析规范正文——规则随规范同文件更新，天然同步。

```markdown
---
checks:
  - cmd: npm run lint --silent
    files: "src/"        # 可选：目录前缀或扩展名（"*.ts"），逗号分隔
    timeout: 60          # 可选：秒，默认 30，硬顶 120
    when: both           # 可选：edit | lifecycle | both（默认 both）
---
```

唯一执行器是 `./.cowork-flow/run spec-check`：

- **三态语义**：`pass`（退出码 0）；`violation` 阻断 `task complete`；`unchecked`（命令缺失、解释器缺失、超时）同样阻断，需显式 `--allow-unchecked` 放行，豁免留痕进 `task.json`。unchecked 永不冒充 pass。
- **两个相位**：`when: edit` 在编辑期就地执行（超时钳制 2.5 秒，违规输出单行提示；具备编辑期 hook 的宿主均已覆盖，其中 zcode 仅主会话），是 best-effort 提示不是门禁；收口期全量执行，未过项阻断状态推进。
- **扫描范围**：`.cowork-flow/spec/` 下的 markdown；`contracts/`、`runtime/`、`schemas/` 三个机器自有子树不参与。
- **模板不带生效声明**：模板无法预知项目命令，而命令缺失会归 `unchecked` 并阻断收口；请把声明写进自建 spec 文件（如 `spec/team-xxx.md`）。

`task start` 后，绑定 spec 的章节索引（h2 标题树）随 stage-contract 注入，规范条目名常驻注意力。完整契约见 `.cowork-flow/spec/contracts/spec-checks.md`。

## 接入原则

- 以目标项目事实为准，不把模板内容当成项目事实
- 保留有价值的流程骨架，删除不存在的场景
- 项目差异写入 `AGENTS.md`、`config.yaml`、`spec/` 或项目自有 Skill；不要恢复第二套流程中枢文档
- 不为了替换项目命令而改写通用 skill
