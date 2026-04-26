# GenericAgent Migration Guide

本文档只覆盖旧 `GenericAgent` 到 `ga_engineered` 的迁移；`free-code` 和
`claw-code` 不进入兼容范围。

## 迁移步骤

1. 保留旧 `GenericAgent/` 目录作为只读参考和 memory 迁移源。
2. 在新工程中安装依赖并运行本地检查：

   ```bash
   cd ga_engineered
   uv sync --extra dev
   uv run gae doctor
   ```

3. 把项目级配置写入 `.generic-agent/settings.json`，把全局配置写入
   `$GENERIC_AGENT_HOME/settings.json`。旧 `mykey.py` 不再作为新运行时配置入口。
4. 使用 `uv run gae status` 确认 provider、model、home、state、auth 路径。
5. 使用 `MemoryService.load_legacy_index("../GenericAgent")` 读取旧
   `GenericAgent/memory`，再通过人工审核后的 `write_reviewed_entry()` 写入新
   memory。
6. 用下面的入口和工具映射逐步替换旧脚本调用。

## 入口迁移

| 旧入口 | 新入口 | 状态 | 说明 |
| --- | --- | --- | --- |
| `python agentmain.py` | `uv run gae chat` | implemented | 新 CLI 已有 slash-command gateway；provider-backed live REPL 由 `AgentLoop` fixture 先锁行为。 |
| `python agentmain.py --task IODIR --input PROMPT` | `uv run gae task IODIR --input PROMPT` | implemented | 保留 `input.txt` / `output.txt` / `[ROUND END]` 文件 I/O 约定，便于批处理脚本迁移。 |
| `python agentmain.py --reflect SCRIPT` | `uv run gae reflect SCRIPT --once` | implemented | 加载 `check()`，触发后写 reflect log，并调用可选 `on_done(result)`。 |
| `/session.key=value` | `/config`、`/model`、后续 settings 写入 | planned | 旧的任意 backend 属性写入不再直接暴露；迁移为显式 settings 和命令。 |
| `/resume` | `/resume` | planned | 命令已注册；后续会接入 SQLite `SessionStore` 的分支和恢复能力。 |

## 工具迁移

| 旧工具 | 新实现或计划 | 状态 | 迁移说明 |
| --- | --- | --- | --- |
| `code_run` | `tools.CodeRunTool` | implemented | Python 临时代码执行已实现；旧 powershell 分支后续迁移到带审批的 `ShellTool`。 |
| `file_read` | `tools.FileReadTool` | implemented | 保留 `path/start/count/keyword/show_linenos`，新增 workspace root 安全边界。 |
| `file_patch` | `tools.FilePatchTool` | implemented | 保留唯一精确替换语义，失败时不猜测位置。 |
| `file_write` | `tools.FileWriteTool` | implemented | 保留 overwrite/append/prepend；新实现显式传 content，不依赖回复块抓取。 |
| `web_scan` | `tools.WebScanTool` | implemented | 保留旧工具名，底层改为 `BrowserBridge`，并加入 HTML 简化和输出预算。 |
| `web_execute_js` | `tools.WebExecuteJsTool` | implemented | 保留旧工具名，浏览器执行结果归一化，适配 TMWebDriver/CDP。 |
| `update_working_checkpoint` | `SessionStore` + `Compaction` + `MemoryService` | planned | 短期工作记忆迁移为 session metadata、压缩摘要和审核后的 memory 写入。 |
| `ask_user` | interactive REPL interrupt | planned | 需要 live REPL 的用户中断通道；不会用自动默认值静默替代。 |
| `start_long_term_update` | `SkillCrystallizer` + `MemoryService` | planned | 长期记忆更新改为 SOP draft，再经人工审核写入 L3 memory。 |

`src/generic_agent_engineered/compat/legacy.py` 中的 `LEGACY_TOOL_MIGRATIONS`
是代码侧权威映射，兼容测试会校验它覆盖旧 `assets/tools_schema.json` 的所有工具。

## 行为兼容测试

`tests/compat/` 覆盖三条旧 Agent 核心路径：

- no-tool final response：模型不调用工具时直接完成。
- `file_read` tool call：模型调用旧名 `file_read`，新 `ToolRegistry` 执行真实
  `FileReadTool`。
- `code_run` tool call：模型调用旧名 `code_run`，新 `CodeRunTool` 执行临时 Python
  脚本并把结果作为 tool message 回传。

这些 fixture 不触网，不依赖真实 provider，用 fake provider 驱动新 `AgentLoop`。
