# 合规执行验证

## 目标
真实验证 cowork-flow 各个门禁在违规场景下是否生效。

## 验证矩阵

| C# | 违规场景 | 预期阻断 |
|----|---------|----------|
| C1 | 无任务 + 编辑文件 | no_task ⛔ STOP |
| C2 | planning 状态 + 编辑文件 | planning 阻断实现 |
| C3 | 无 tdd.jsonl + task review | TDD gate 阻断 |
| C4 | tdd.jsonl 字段不全 + task review | test_intent 阻断 |
| C5 | task complete 缺少 check | transition 阻断 |
| C6 | 子代理尝试 spawn 其他 agent | authority block |
| C7 | 子代理绑定错误 key | bind reject |
