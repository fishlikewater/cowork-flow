# Release 脚本设计

## 分级

本变更归类为 L2。原因是它修改 npm 包发布链路，影响版本升级、验证顺序和实际发布行为，属于发布风险相关变更。

## 方案选择

采用仓库内 shell 脚本 `scripts/release.sh`，并在 `package.json` 中暴露：

```json
{
  "scripts": {
    "release": "sh scripts/release.sh"
  }
}
```

脚本使用 npm 原生命令完成核心动作：

- `npm run test:all` 作为发布前质量门禁。
- `npm version <type>` 作为版本升级来源，避免手写 JSON 和锁文件。
- `npm publish` 作为实际发布动作，继续使用 npm 的认证、版本冲突和 registry 校验。

## 取舍

### 方案 A：直接使用 npm version 和 npm publish

优点：

- 最少自定义逻辑。
- 自动同步 `package.json` 与 `package-lock.json`。
- 保持 npm 默认提交与 tag 行为，便于追踪发布版本。

缺点：

- 如果 `npm publish` 因网络或权限失败，版本提交和 tag 可能已经产生，需要修复凭据后重试 `npm publish`。

### 方案 B：脚本自行修改 package.json 与 package-lock.json

优点：

- 可以完全控制写文件和提交时机。

缺点：

- 容易重新实现 npm 已有语义化版本逻辑。
- 更容易遗漏 lockfile 细节。
- 维护成本高于当前需求。

### 方案 C：只改 GitHub Actions，由 CI 自动 bump

优点：

- 本地发布更少。

缺点：

- 会显著扩大发布治理范围。
- 需要处理 CI 写回版本提交、tag、权限和 release 触发循环。
- 超出“npm 推送包不用手动升级版本号”的当前目标。

## 推荐结论

采用方案 A。它用 npm 自身作为版本升级和发布的事实来源，仓库只封装顺序、参数校验和文档说明，符合简单优先和外科手术式改动原则。

## 测试策略

- 新增 Node 单元测试通过 fake npm 执行 shell 脚本，验证默认 patch、显式版本类型、非法参数和失败短路。
- 新增包元数据测试，确保 `package-lock.json` 根包版本与 `package.json` 一致。
- 运行 `npm run test:all` 验证 Node 测试、模板测试和 npm pack 内容检查。
