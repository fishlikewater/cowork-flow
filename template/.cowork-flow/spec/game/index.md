# 游戏开发规范

> 适用于游戏项目的通用约定和最佳实践。与 `backend/` 和 `frontend/` 规范同层，作为 cowork-flow 中游戏开发任务的领域指南。

## 目录

| 文件 | 作用 |
|------|------|
| `engine-guidelines.md` | 引擎选型、ECS vs OOP、场景/关卡组织、插件策略 |
| `asset-pipeline.md` | 资产文件组织、构建阶段、LOD 策略、版本控制 |
| `performance-guidelines.md` | 帧率目标、内存预算、GC 管理、渲染优化、分析工作流 |
| `multiplayer-guidelines.md` | 网络模型、同步策略、延迟补偿、匹配服务 |

## 读取顺序

1. `engine-guidelines.md` — 项目启动或引擎选型时优先阅读
2. `asset-pipeline.md` — 配置构建管线或添加资产前
3. `performance-guidelines.md` — 做性能相关实现或优化前
4. `multiplayer-guidelines.md` — 涉及网络同步的任务前

## 与项目规范的关系

项目级别约定优先于本规范。当具体游戏项目有自己的 `GAME_DESIGN.md` 或 `CONVENTIONS.md` 时，以项目文档为准。本规范提供通用基线。
