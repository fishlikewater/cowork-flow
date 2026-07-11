## 字符集编码要求

### Windows 平台编码规范

- **环境初始化**：在执行任何 `PowerShell` 脚本或命令前，优先执行
  `$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8`，强制统一当前会话的输入输出编码。
- **绝对强制使用 UTF-8**：包含但不限于修改源代码、读写配置、生成文本、日志记录等所有涉及字符流输入输出的操作，都必须显式指定
  `UTF-8` 编码，严禁依赖系统默认编码（如 `GBK/CP936`）。
- **PowerShell 读写规范**：
  - 使用 `Get-Content` 和 `Set-Content` 时，必须显式添加 `-Encoding UTF8` 参数。
  - 使用 `Out-File` 时，必须显式添加 `-Encoding UTF8` 参数。
  - 尽量避免使用重定向符号 `>` 进行文本输出，推荐使用 `Set-Content -Encoding UTF8` 替代。
- **无 BOM 格式约束**：除非目标系统（如旧版 Windows 记事本或特定遗留软件）明确要求，否则生成的 `UTF-8` 文本文件**必须不带
  `BOM`
  **。在 PowerShell 中，建议使用
  `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $false))` 来确保无 `BOM` 写入。
- **Python 读写规范**：所有 `open()` 函数调用必须显式包含 `encoding="utf-8"` 参数（例如
  `open("file.txt", "r", encoding="utf-8")`）。
- **Node.js 读写规范**：在 `fs.readFile` 或 `fs.writeFile` 中，必须显式指定 `{ encoding: "utf8" }` 选项。
- **Java 读写规范**：
  - 严禁使用 `FileReader` 或 `FileWriter`（它们会隐式使用系统默认编码）。必须使用 `FileInputStream` / `FileOutputStream` 配合
    `InputStreamReader` / `OutputStreamWriter`，并显式传入 `StandardCharsets.UTF_8`。
  - 在使用 `Files.readAllLines` 或 `Files.write` 时，必须显式传入 `StandardCharsets.UTF_8` 参数。
  - 涉及 `Scanner` 读取文件时，必须指定 `new Scanner(file, "UTF-8")`。
- **Go 语言读写规范**：使用 `os.Create` 或 `os.OpenFile` 后，建议使用 `bufio` 或 `ioutil` 时确保写入的是 `UTF-8` 字节流；若涉及
  Windows 特定 API，需注意转换。
- **文件头检查**：在修改现有文件前，应检查文件当前的编码格式，避免将非 `UTF-8` 文件错误地以 `UTF-8` 解析导致乱码损坏。
