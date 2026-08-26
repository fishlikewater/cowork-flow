# 思考指引

> 本目录不讲实现细节，只提醒最容易出问题的思考点；主要供 brainstorming 与 task-planning 在编码前使用。

---

## 常见风险

- 模块边界被打穿
- 权限与业务授权混在一起
- 跨层契约只改了一半
- 新增一套重复常量、错误码、查询模式
- 接口、数据结构、任务流转没有同步更新

---

## 使用方式

- 需求不清晰时，在 brainstorming 阶段用这些指引收敛目标、非目标、边界和验收标准
- 编写计划时，在 task-planning 阶段把选中的结论写进 decision-anchor 或任务计划
- 写代码前先看 [编码前检查表](./pre-implementation-checklist.md)
- 涉及跨模块、异步链路、权限或状态流转时，看 [跨层思考指引](./cross-layer-thinking-guide.md)
- 涉及公共能力、常量、错误码、查询模板、校验逻辑时，看 [代码复用思考指引](./code-reuse-thinking-guide.md)

---

## 最小动作

修改前先搜索：

```bash
rg "关键字"
```
