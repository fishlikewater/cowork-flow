# 后端异常处理规范

<!--
本 spec 支持 frontmatter `checks:` 声明检查命令（规范挂命令契约见
spec/contracts/spec-checks.md）。模板自带的声明由上游维护、sync 会覆盖
本地修改；请把实际声明写进自建 spec 文件。示例：

---
checks:
  - cmd: python scripts/check_error_codes.py
    files: "src/"
    when: lifecycle
---

-->

## 目标

- 调用方能稳定感知错误
- 内部错误与外部错误边界清晰

## 推荐做法

- 统一定义错误码或错误类型
- 参数校验错误、业务错误、系统错误分层处理
- 对外返回稳定结构，对内保留足够上下文
- 不把底层异常原样泄露给调用方

## 典型检查项

- 是否区分“可预期业务失败”和“系统异常”
- 是否保留 traceId / requestId / correlationId
- 是否有统一异常兜底
- 是否记录了必要但不过量的日志
