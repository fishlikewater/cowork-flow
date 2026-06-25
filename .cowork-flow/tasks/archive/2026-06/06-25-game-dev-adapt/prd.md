# PRD: 游戏开发流程适配

## 目标

在现有 cowork-flow 中补充游戏开发领域知识覆盖，创建 `game-design` skill 和 `.cowork-flow/spec/game/` 规范目录。

**非目标：**
- 不创建新固定代理
- 不修改 workflow.md、AGENTS.md 或现有 3 固定代理
- 不包含具体游戏引擎的 API 绑定
- 不包含 3D 建模/贴图/音频等非代码岗位的工作流

## 验收标准

| ID | 描述 |
|----|------|
| AC-01 | `game-design` skill 可从 IDE/CLI 调用，frontmatter 正确 |
| AC-02 | `.cowork-flow/spec/game/` 目录至少包含 index.md、engine-guidelines.md、asset-pipeline.md、performance-guidelines.md、multiplayer-guidelines.md |
| AC-03 | 现有流程不被破坏（无文件被修改） |
| AC-04 | skill 内容覆盖游戏架构、资产管线、性能分析、多人游戏领域 |

## 范围

### In-Scope

- `.claude/skills/game-design/SKILL.md`
- `.cowork-flow/spec/game/index.md`
- `.cowork-flow/spec/game/engine-guidelines.md`
- `.cowork-flow/spec/game/asset-pipeline.md`
- `.cowork-flow/spec/game/performance-guidelines.md`
- `.cowork-flow/spec/game/multiplayer-guidelines.md`

### Out-of-Scope

- 修改现有同事-flow 基础设施
- 添加测试脚本
- 添加新依赖
