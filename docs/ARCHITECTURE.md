# GenericAgent Architecture

本文档只描述当前工作区中的 `GenericAgent/` 子项目架构，不包含其他子项目或兼容实现。

架构图见 [architecture-diagram.html](./architecture-diagram.html)。

## 1. 项目定位

`GenericAgent` 是一个极简、自进化的本地自治 Agent 框架。它的核心设计是：

```text
LLM 会话
  -> Agent turn loop
  -> 原子工具调用
  -> 本地环境执行
  -> 工作记忆 / 长期记忆更新
  -> 下一轮推理或最终回复
```

项目把大量能力留给运行时自我扩展：模型通过 `code_run`、文件工具、浏览器工具、ADB/系统脚本等能力探索新任务路径，再把成功经验沉淀到 `memory/` 下的 SOP、skill 和长期记忆中。

## 2. 目录结构

```text
GenericAgent/
├── agentmain.py             # 主运行器，任务队列、LLM client、CLI/task/reflect 模式
├── agent_loop.py            # Agent turn loop 与 tool dispatch 核心
├── ga.py                    # GenericAgentHandler 与原子工具实现
├── llmcore.py               # LLM API/session 适配层
├── TMWebDriver.py           # 真实浏览器控制桥
├── simphtml.py              # 页面简化、JS 执行结果处理辅助
├── launch.pyw               # 桌面启动入口
├── frontends/               # Streamlit、Qt、Telegram、QQ、飞书、微信等前端
├── reflect/                 # 反射/调度任务
├── memory/                  # L1-L4 记忆、SOP、技能、工具脚本
├── assets/                  # system prompt、tool schema、浏览器扩展、模板资源
├── plugins/                 # 可选 tracing 等插件
└── tests/                   # LLM/provider 相关测试
```

## 3. 启动与入口层

主要入口是 `agentmain.py` 中的 `GeneraticAgent`。

`GeneraticAgent` 负责：

- 初始化语言环境 `GA_LANG`。
- 从 `mykey.py` 或 `mykey.json` 读取模型配置。
- 根据配置创建一个或多个 LLM client。
- 维护任务队列 `task_queue`、历史摘要 `history`、当前 handler、停止信号。
- 把用户请求、机器人消息、文件任务或反射任务统一送入 Agent loop。

运行模式：

- 交互 REPL：直接运行 `python agentmain.py`。
- 一次性/文件任务：`--task IODIR`，通过 `input.txt`、`output*.txt`、`reply.txt` 交换。
- 反射模式：`--reflect SCRIPT`，周期执行脚本 `check()`，触发后投递任务。
- 后台模式：`--bg`，生成后台进程并写日志。
- GUI/前端：`launch.pyw` 和 `frontends/*.py` 包装同一个 Agent 核心。

## 4. Agent Loop

`agent_loop.py` 提供核心循环：

- `agent_runner_loop(...)` 构建初始 system/user messages。
- 每一轮调用 `client.chat(messages, tools=tools_schema)`。
- 解析模型输出中的 tool calls；如果没有工具调用，自动注入 `no_tool`。
- 调用 `handler.dispatch(tool_name, args, response)`。
- 工具返回 `StepOutcome`，决定继续、退出、完成或给下一轮追加 prompt。
- 每轮结束调用 `turn_end_callback(...)`，记录简短历史摘要、注入工作记忆、处理重试/计划/长期记忆提示。

关键数据结构：

- `StepOutcome.data`: 工具执行结果。
- `StepOutcome.next_prompt`: 下一轮给模型的增量提示。
- `StepOutcome.should_exit`: 是否中断任务，例如 `ask_user`。
- `BaseHandler.dispatch`: 通过 `do_<tool_name>` 命名约定分派工具。

这个 loop 很薄，主要负责调度；实际能力由 LLM session 和 `GenericAgentHandler` 承担。

## 5. LLM Session 层

`llmcore.py` 把不同模型 API 统一成 `client.chat(...)`：

- `ClaudeSession`: Anthropic Messages API 路径。
- `LLMSession`: OpenAI-compatible chat/responses 路径。
- `NativeClaudeSession` / `NativeOAISession`: 原生 tool calling 路径。
- `MixinSession`: 多模型混合/故障转移。
- `ToolClient`: 将工具协议编码进文本 prompt，并解析 `<tool_use>` 块。
- `NativeToolClient`: 使用模型原生工具调用格式。

重要职责：

- SSE 流解析：Anthropic、OpenAI Chat Completions、OpenAI Responses。
- 工具 schema 转换：OpenAI-style schema 与 Claude-style schema 互转。
- history 管理：压缩 `<thinking>`、`<tool_use>`、`<tool_result>` 等旧内容。
- token 控制：上下文过长时裁剪旧消息并保留最近上下文。
- API URL 兼容：自动拼接 `/v1/messages`、`/v1/chat/completions`、responses 等路径。

## 6. 工具执行层

`ga.py` 定义 `GenericAgentHandler`，是 Agent 真实行动能力的核心。

主要工具：

- `code_run`: 执行 Python 或 shell。Python 代码写入临时 `.ai.py` 文件执行；shell 走 `bash -c` 或 PowerShell。
- `file_read`: 分段读取文件，支持起始行、keyword 搜索、行号显示和近似文件建议。
- `file_write`: 覆盖、追加、前置写文件，内容从 `<file_content>` 或代码块提取。
- `file_patch`: 通过唯一旧文本块替换实现精确补丁。
- `web_scan`: 读取当前浏览器 tabs 与简化 HTML。
- `web_execute_js`: 在真实浏览器页面执行 JS，支持保存完整返回结果。
- `ask_user`: 中断并等待人工输入。
- `update_working_checkpoint`: 写入本任务临时工作记忆。
- `start_long_term_update`: 任务结束时触发长期记忆沉淀。
- `no_tool`: 模型未调用工具时的自动完成/重试/保护逻辑。

工具 schema 位于：

- `assets/tools_schema.json`
- `assets/tools_schema_cn.json`

## 7. 浏览器控制层

`TMWebDriver.py` 与 `assets/tmwd_cdp_bridge/` 组成真实浏览器控制桥：

```text
GenericAgentHandler.web_scan/web_execute_js
  -> TMWebDriver
  -> local HTTP/WebSocket service
  -> browser extension
  -> active browser tab
  -> DOM snapshot or JS execution result
```

设计重点：

- 使用真实浏览器 tab，保留用户登录态。
- `web_scan` 通过 `simphtml.py` 将页面压缩为更适合模型读取的主体内容。
- `web_execute_js` 优先用于精确操作页面，减少全量 DOM 观察。
- 浏览器扩展配置在 `assets/tmwd_cdp_bridge/`，首次运行会生成 `config.js`。

## 8. 记忆系统

`memory/` 是 GenericAgent 自进化能力的核心。

分层结构：

- L1 Insight Index：快速路由和记忆索引，如 `global_mem_insight.txt`。
- L2 Global Facts：长期稳定事实，如环境、配置、偏好、路径。
- L3 Task Skills / SOPs：可复用任务流程，如 `*_sop.md`、`skill_search/SKILL.md`。
- L4 Session Archive：会话归档与压缩，如 `L4_raw_sessions/`。

运行时注入：

- `agentmain.py:get_system_prompt()` 读取 `assets/sys_prompt*.txt`。
- `ga.py:get_global_memory()` 注入当前 memory 结构、insight 和固定格式说明。
- `turn_end_callback()` 在长任务中周期性追加全局记忆，避免任务漂移。

沉淀流程：

```text
任务成功
  -> start_long_term_update
  -> 读取 memory_management_sop.md
  -> 判断是环境事实还是复杂任务经验
  -> 更新 L1/L2 或新增/修改 L3 SOP
```

## 9. 前端与机器人适配

`frontends/` 下的不同入口共享同一个 Agent 核心：

- `stapp.py`, `stapp2.py`: Streamlit UI。
- `qtapp.py`: Qt 桌面 UI。
- `tgapp.py`: Telegram bot。
- `qqapp.py`: QQ bot。
- `fsapp.py`: 飞书。
- `wecomapp.py`: 企业微信。
- `dingtalkapp.py`: 钉钉。
- `wechatapp.py`: 微信相关入口。
- `chatapp_common.py`: 多聊天前端复用逻辑。
- `continue_cmd.py`: 会话恢复命令支持。

前端基本模式：

```text
frontend receives message
  -> agent.put_task(query, source=...)
  -> consume display queue
  -> stream next/done chunks to user
```

## 10. 插件与可观测性

`plugins/langfuse_tracing.py` 是可选 tracing 插件。`llmcore.py` 在加载 `mykey` 时如果发现 `langfuse_config`，会尝试导入该插件。

这类插件不改变核心 loop，只扩展观测、记录或外部集成。

## 11. 核心运行链路

```text
User / frontend
  -> GeneraticAgent.put_task()
  -> GeneraticAgent.run()
  -> get_system_prompt()
      -> sys_prompt + global memory
  -> agent_runner_loop()
      -> llmclient.chat()
      -> parse tool calls
      -> GenericAgentHandler.dispatch()
      -> tool execution
      -> StepOutcome
  -> turn_end_callback()
      -> short history
      -> working memory
      -> retry/long-term memory hints
  -> final response or next turn
```

## 12. 架构取舍

- 极简闭环：核心 loop 不负责复杂业务逻辑，只负责模型与工具的 turn 调度。
- 工具原子化：系统能力被压缩成少数通用工具，模型按需组合。
- 真实环境优先：通过本地 shell、文件系统、真实浏览器、ADB 等触达用户机器。
- 记忆驱动演化：不预置大量技能，而是在任务成功后沉淀 SOP 和事实。
- 多模型兼容：通过 `llmcore.py` 抹平 Claude、OpenAI-compatible、native tool calling 的差异。
- Token 经济性：压缩旧 thinking/tool 标签，裁剪超长 history，只把必要 memory 注入 prompt。

## 13. 本次产物

- [docs/ARCHITECTURE.md](./ARCHITECTURE.md): 仅 `GenericAgent/` 本体架构文档。
- [docs/architecture-diagram.html](./architecture-diagram.html): 仅 `GenericAgent/` 本体架构图。

已安装的架构图 skill：

- `.codex/skills/architecture-diagram-generator/`: 用户要求克隆的上游仓库源码。
- `.codex/skills/architecture-diagram/`: 可被 Codex 识别的实际 skill 目录。
