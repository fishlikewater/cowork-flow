# 决策锚点：运行时热点复杂度收口

## 目标

- 修复本地 bootstrap 漂移测试在 clean checkout 下的边界问题。
- 拆分 `task_parser.py::build_parser`，把 CLI 子命令注册分组到 helper。
- 拆分 `task_lifecycle.py::execute`，把生命周期阶段处理拆成小函数。
- 拆分 Party Mode V2 的响应/推进/完成热点函数，降低命令层复杂度。
- 拆分 skill registry entry normalization，保持 registry 输出语义不变。

## 非目标

- 不改变工作流状态机、Party Mode board 协议、registry schema 或 CLI 参数契约。
- 不删除合法历史迁移测试、obsolete 清理清单或 adapter fallback 契约。
- 不引入兼容期或旧入口回退。

## 验收标准

- AC-001: 本地 bootstrap 漂移测试在缺少 root 自举文件时 skip，而不是失败。
- AC-002: 目标热点函数被拆分，复杂度门禁无新增 warning。
- AC-003: 相关聚焦测试通过。
- AC-004: `npm run test:all` 通过。
