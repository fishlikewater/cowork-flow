# project-context 使用证明

## 扫描命令

```powershell
codegraph explore "project-context project_context run.py copy-template sync init tests current workflow usage"
rg --encoding utf-8 -n --hidden "project-context|project_context|project-context\.md" . -g '!node_modules/**' -g '!.git/**'
rg --encoding utf-8 -n --hidden "project-context|project_context|project-context\.md" .cowork-flow .codex .claude .opencode template src test tests README.md package.json -g '!node_modules/**' -g '!.git/**' -g '!.cowork-flow/tasks/archive/**'
rg --encoding utf-8 -n --hidden "project-context|project_context|project-context\.md" .codex .claude .opencode .cowork-flow/adapters template/.cowork-flow/adapters -g '!node_modules/**' -g '!.git/**'
```

## 删除前结论

- CodeGraph 显示 `.cowork-flow/scripts/run.py` / `template/.cowork-flow/scripts/run.py` 无 indexed 直接依赖，`project-context` 只作为命令映射暴露。
- CodeGraph 显示 `src/lib/copy-template.js` 只由 `src/commands/init.js` 和 `src/commands/sync.js` 使用，因此下游旧文件删除应通过 sync 的 obsolete 清单收口。
- hook、adapter、host 资产扫描无 `project-context` / `project_context` / `project-context.md` 命中。
- 活跃引用集中在 README、workflow 状态表、runner 命令映射、生成脚本自身，以及保护旧行为的测试。
- 历史任务归档和 workspace journal 中的命中是历史记录，不属于当前流程调用。

## 删除后结论

```powershell
rg --encoding utf-8 -n --hidden "project-context|project_context|project-context\.md" . -g '!node_modules/**' -g '!.git/**' -g '!.cowork-flow/tasks/archive/**' -g '!.cowork-flow/workspace/**'
rg --encoding utf-8 -n --hidden "project-context|project_context|project-context\.md" .codex .claude .opencode .cowork-flow/adapters template/.cowork-flow/adapters -g '!node_modules/**' -g '!.git/**'
```

- 活跃 runtime、README 和 workflow 不再暴露 `project-context` 命令或 `.cowork-flow/project-context.md` 状态文件。
- 当前剩余命中只用于测试删除行为、sync 删除旧文件，以及本任务证据记录。
- hook/adapters 删除后扫描仍无命中。
