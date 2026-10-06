# Evidence Completion Contract

**任务完成从"流程走完"升级为"证据齐全"：decision-anchor 的验收标准（AC）是机器可查询的事实，完成门禁校验每个 AC 的证据记录存在性。**

机器只裁决存在性事实（AC 声明、勾选状态、证据条目有无）；一条证据是否真正证明对应 AC，由 review 判断。

## 证据记录：`evidence.jsonl`

任务目录下的追加式 JSONL 文件，由实现方（主会话或子代理）在实现过程中写入，runtime 只读：

```json
{"ac": "AC-001", "kind": "test", "ref": "tests/test_ac_evidence.py", "note": "覆盖计算三态断言", "recordedAt": "2026-10-06", "by": "cwf-cli-1004"}
```

| 字段 | 必填 | 含义 |
|---|---|---|
| `ac` | 是 | 对应的 AC id（`AC-xxx`，与 decision-anchor 一致） |
| `kind` | 是 | `test`（自动化测试）、`command`（命令及退出码）、`manual`（手工验证记录） |
| `ref` | 是 | 证据指向：测试文件/用例、命令、手工记录位置；非空字符串 |
| `note` | 否 | 核心断言一句话 |
| `recordedAt` | 否 | ISO 日期 |
| `by` | 否 | 写入者会话/执行者标识 |

坏行、缺字段、未知 `kind` 的记录被读取端跳过（与 context JSONL 容错一致），门禁只看有效记录。

## 完成门禁

`task next <dir> --run` 的完成动作在直接生命周期检查中追加两条稳定 code：

| code | 触发事实 | 豁免 |
|---|---|---|
| `LIFECYCLE-AC-001` | 存在未勾选的 AC 行 | 无——完成工作本身，或勾选已完成的行 |
| `LIFECYCLE-AC-002` | 存在已声明但无任何有效证据记录的 AC | `--allow-missing-evidence`（记入 task.json `meta.evidenceExempt`，含 `at` 与 `missing`） |

- 两个 code 可同时出现；`--allow-missing-evidence` 只豁免 `LIFECYCLE-AC-002`。
- **兼容路径**：decision-anchor 缺失或未声明任何 AC 行的任务（全部存量任务）不触发本门禁；ac_evidence 模块不可读时同样降级为不阻断。
- 豁免留痕 `meta.evidenceExempt` 与 spec-check 的 `specCheckExempt` 同型：重试不累积，最新一次完成结果为准。

## 注入与事实视图

- decision-anchor 注入块：声明了 AC 的任务在 `Acceptance:` 行后追加一行 `AC evidence: <有证据数>/<总数>`，有缺失时附 ` missing=<id 逗号列表，最多 5 个>`；三线（Python / zcode shim / opencode 插件）逐字节同格式，由矩阵测试锁定。
- `run state <task> --json` / MCP 事实视图：`evidenceCoverage: {total, withEvidence, missing[]}`；未声明 AC 时为 `null`。

## 边界

- runtime 不代写证据，不执行 AC 对应命令"代打"记录。
- 不解析 AC 正文语义；`AC-xxx` 行的勾选框缺失时按未完成解析。
- 本契约不改变 spec-check 语义；MCP 写工具仍默认拒绝（`fact-layer-access.md`）。
