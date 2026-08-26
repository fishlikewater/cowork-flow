# Security Quick Reference

> 安全快速参考。当处理用户输入/认证/数据存储/外部集成时按需加载。

契约: ERROR_OUTPUT_AS_DATA_V1 (详见 .cowork-flow/spec/contracts/error-output-as-data.md)

## 输入验证

- 所有外部输入在边界验证（API 入口、文件上传、CLI 参数）
- 错误信息不泄漏内部实现细节（栈追踪、路径、库版本）
- 参数化查询，禁止字符串拼接 SQL
- 长度/类型/范围白名单，而非仅黑名单

## 认证授权

- 认证状态不在客户端存储（仅 httpOnly secure cookie）
- 权限检查在每次受保护操作时执行（不依赖前端隐藏）
- 认证失败不区分用户名错/密码错（统一提示"认证失败"）
- Session 有过期时间 + rotation on privilege change

## 依赖与供应链

- 第三方依赖来自可信来源
- 无已知 CVE（`pip audit` / `npm audit`）
- Lockfile 提交到版本控制

## 数据与隐私

- 日志中不出现敏感数据（密码、token、PII）
- 传输加密（TLS），存储加密（bcrypt/argon2）
- 错误输出视为不可信数据（参见 ERROR_OUTPUT_AS_DATA_V1）

## OWASP Top 10 快速映射

| 编号 | 类别 | 检查 | 缺失风险 |
|---|---|---|---|
| A01 | 注入 | 参数化查询 | 数据泄露或丢失 |
| A02 | 失效认证 | bcrypt + session rotation | 账号劫持 |
| A03 | 敏感数据暴露 | 传输加密+存储加密+不泄漏 | 数据泄露 |
| A04 | XXE | 禁用外部实体解析 | XML 注入 |
| A05 | 失效访问控制 | 每次请求重新验权 | 越权操作 |
| A06 | 安全配置错误 | 默认安全+无调试头 | 信息泄漏 |
| A07 | XSS | 输入输出编码+CSP | 浏览器端代码执行 |
| A08 | 不安全反序列化 | 不反序列化不可信数据 | RCE |
| A09 | 已知漏洞组件 | 定期 audit | 已知 exploit |
| A10 | 未授权重放 | nonce + rate limit | 自动化滥用 |

## 参见

- `spec/contracts/error-output-as-data.md` — 防御 prompt injection
- `skills/test-first/SKILL.md` — 安全回归测试证据
