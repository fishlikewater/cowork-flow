# 后端目录结构规范

## 目标

- 模块职责清晰
- 包结构稳定
- 新人和 AI 能快速定位代码

## 推荐做法

- 按业务能力或边界拆模块，不按“工具类型”滥拆
- Controller / API 只做参数接收、鉴权入口和响应编排
- Service / UseCase 承接业务规则
- Repository / DAO 承接持久化访问
- Domain Model / Entity / Aggregate 保持边界清晰

## 命名建议

- 模块名体现业务边界，不体现实现细节
- 包名与目录名统一小写
- 同一层命名保持后缀一致，例如 `Controller`、`Service`、`Repository`

## 不建议

- 一个模块同时承担多个无关业务
- 在 Controller 中堆业务逻辑
- 在公共模块中混入业务特化逻辑
