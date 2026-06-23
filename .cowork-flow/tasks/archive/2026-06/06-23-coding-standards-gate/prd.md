# 编码规范强约束与 UTF-8 校验 PRD

## 目标

让编码规范从文档提醒升级为可阻断的自动校验，尤其覆盖 UTF-8 读写和 Windows/Python/Node 路径。

## 范围

### In Scope

- 统一 git snapshot，覆盖 modified/staged/untracked。
- 实现编码规范 validator。
- 修复现有 validator 自身的隐式编码问题。
- 将编码规范 gate 接入 review/complete。

### Out of Scope

- TDD skill。
- 测试意图审查。

## 验收标准

- AC-001: Python/PowerShell/Node 的默认编码违规可被阻断。
- AC-002: 读写文本未显式 UTF-8 的新增改动可被识别。
- AC-003: validator 自身在 Windows 上不依赖默认编码。
- AC-004: modified、staged、untracked 文件都会进入编码规范扫描。

## 相关文件

- `.cowork-flow/scripts/common/coding_standards.py`
- `.cowork-flow/scripts/common/git_snapshot.py`
- `.cowork-flow/scripts/common/validate_coding_standards.py`
- `.cowork-flow/scripts/common/validate_rules.py`
- `tests/test_flow_script_paths.py`
- `.cowork-flow/spec/backend/encoding-guidelines.md`
- `tests/fixtures/coding-standards/implicit-open.py`
- `tests/fixtures/coding-standards/implicit-read-file.js`
- `tests/fixtures/coding-standards/implicit-get-content.ps1`
- `test/coding-standards.test.js`

## 验证方式

```powershell
python -m unittest tests.test_flow_script_paths -v
npm test -- coding-standards
git diff --check
```
