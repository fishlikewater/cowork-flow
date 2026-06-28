# Backend behavior

- `writing-plans` skill 生成的 plan 文件包含可执行步骤，每个步骤有明确的 file、action、verify、expected 字段
- `cowork-implement` 读取当前任务的 plan 文件并按步骤执行
- `cowork-check` 读取当前任务的 plan 文件并按步骤检查
- plan 文件路径通过 task.json 的 plan 字段关联，或通过 plan 文件中的 task 字段反向关联
