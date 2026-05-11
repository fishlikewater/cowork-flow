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

## 活跃开发者

| 开发者 | 最近活跃 | 会话数 | 当前文件 |
|--------|----------|--------|----------|
| (none yet) | - | - | - |

---

## 开始使用

### 新开发者

```bash
python3 ./.trellis/scripts/init_developer.py <your-name>
```

### 已初始化开发者

```bash
python3 ./.trellis/scripts/get_developer.py
cat .trellis/workspace/$(python3 ./.trellis/scripts/get_developer.py)/index.md
```

---

## 记录约定

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

**语言约定**：新增记录默认使用中文；如果项目统一使用英文，请在复制后整体改口径。
