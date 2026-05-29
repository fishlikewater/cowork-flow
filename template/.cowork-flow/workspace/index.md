# 工作区索引

> 记录所有开发者的 AI 会话工作记录

---

## 概览

此目录用于跟踪项目中所有开发者与 AI 协作时产生的记录。

### 目录结构

```text
workspace/
|-- index.md              # 当前文件：主索引
+-- {developer}/          # 每个开发者的独立目录
    |-- index.md          # 个人索引与会话历史
    +-- journal-N.md      # 顺序递增的日志文件
```

---

## 状态来源

此文件只说明 workspace 的用途和目录约定，不维护开发者状态。

真实状态以以下位置为准：

- 当前开发者：`.cowork-flow/.developer`
- 当前开发者索引：`.cowork-flow/workspace/<developer>/index.md`
- 当前 journal：`.cowork-flow/workspace/<developer>/journal-*.md`
- 会话恢复摘要：`./.cowork-flow/run resume`

---

## 开始使用

### 新开发者

```bash
./.cowork-flow/run init-developer <your-name>
```

### 已初始化开发者

```bash
./.cowork-flow/run get-developer
cat .cowork-flow/workspace/$(./.cowork-flow/run get-developer)/index.md
```

---

## 记录约定

- workspace 仅用于记录会话 journal，不作为任务流程控制面。
- 当前任务状态以 `.cowork-flow/tasks/` 和 `run resume` 输出为准。
- 单个 journal 文件最多 `2000` 行
- 超过上限后，创建 `journal-{N+1}.md`
- 新建文件后，更新个人 `index.md`

---

## 会话模板

```markdown
## 会话 {N}：{标题}

**日期**：YYYY-MM-DD
**任务**：{task-name}

### 摘要

{一句话摘要}

### 主要变更

- {变更 1}
- {变更 2}

### Git 提交

| 哈希 | 说明 |
|------|------|
| `abc1234` | {commit message} |

### 验证

- [OK] {验证结果}

### 状态

[OK] **已完成** / # **进行中** / [P] **阻塞**

### 后续动作

- {后续动作 1}
- {后续动作 2}
```

---

**语言约定**：新增记录默认使用中文；如果项目统一使用英文，请整体改口径。
