## 日期前缀 slug

### 场景：task create 自动补日期前缀

- Given 用户传入不带日期前缀的 slug `demo-task`
- When 用户执行 `task create`
- Then 任务目录名应为 `<MM-DD>-demo-task`

### 场景：task create 保留已有日期前缀

- Given 用户传入已带日期前缀的 slug `<MM-DD>-demo-task`
- When 用户执行 `task create`
- Then 任务目录名应为 `<MM-DD>-demo-task`
- And 不应生成 `<MM-DD>-<MM-DD>-demo-task`

### 场景：change create 自动补日期前缀

- Given 用户传入不带日期前缀的 slug `demo-change`
- When 用户执行 `change create`
- Then change 目录名应为 `<MM-DD>-demo-change`

### 场景：change create 保留已有日期前缀

- Given 用户传入已带日期前缀的 slug `<MM-DD>-demo-change`
- When 用户执行 `change create`
- Then change 目录名应为 `<MM-DD>-demo-change`
- And 不应生成 `<MM-DD>-<MM-DD>-demo-change`
