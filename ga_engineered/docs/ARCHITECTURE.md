# GenericAgent Engineered Architecture

本文档描述 `ga_engineered` 的目标架构。它是 `GenericAgent` 的新工程化实现目录，不直接修改旧运行时。

## 设计目标

- 保留 `GenericAgent` 的最小 Agent loop、原子工具、自进化记忆思想。
- 用 Python 重新设计清晰边界：配置、Auth、Provider、Runtime、Tool、Command、UI、State。
- 用 `uv` 管理依赖、运行、测试和开发环境。
- 借鉴 `free-code` 的命令注册、动态命令加载、feature gate、CLI bootstrap 分层。
- 借鉴 `hermes-agent` 的 provider registry、OAuth/auth store、profile/home 目录、Rich/prompt-toolkit CLI 表现层。

## 目标分层

```text
CLI / TUI
  -> Command Registry
  -> Application Services
  -> Agent Runtime
  -> LLM Provider Strategy
  -> Tool Runtime
  -> State / Memory / Auth Stores
```

## 模块边界

- `config.py`: 解析环境变量、home 目录、项目配置路径、运行时设置。
- `providers/`: Provider Strategy 接口、静态 provider registry、具体 client、tool schema 转换和 provider 错误映射。
- `runtime/`: provider-neutral message、tool call、tool result、response 和 event 数据模型。
- `tools/`: provider-neutral tool schema、permission metadata、tool execution 和 enable/disable registry。
- `auth/`: API key、OAuth PKCE、token refresh、auth.json 原子写入。
- `commands/`: slash command 元数据、解析、路由和 handler 包。`registry.py`
  只声明命令；`session.py`、`config.py`、`tools.py`、`memory.py`、`skills.py`
  实现业务处理，供 CLI help、autocomplete、gateway 复用。
- `state/`: SQLite session store、schema、message persistence、FTS search 和
  session branch 管理。
- `memory/`: L1/L2/L3/L4 layered memory index、旧 GenericAgent memory 迁移读取、
  人工审核后的 memory 写入服务。
- `skills/`: 成功任务结构化摘要到 SOP draft 的 crystallizer，以及 L3 memory
  duplicate detection。
- `compat/`: 旧 `GenericAgent` 入口和工具 schema 的迁移映射，以及 `task` /
  `reflect` 文件 I/O 兼容 shim。
- `engine.py`: composition root，装配 settings、providers、state。
- `cli/`: CLI bootstrap package，`--version` 快速路径不初始化 runtime；
  `doctor.py` 检查 provider/auth/state/tool/command 环境；`status.py` 输出
  session、provider、model、home、state 和 auth 路径。
- `ui/`: Rich/plain console、startup banner、statusbar、tool progress spinner、
  prompt-toolkit slash command completer 和 Python TUI shell；非 TTY 或缺少可选
  终端依赖时自动降级到 plain text。

## Provider 策略

每个 provider 由 `ProviderSpec` 描述：

- `transport`: `openai_chat`、`openai_responses`、`anthropic_messages`、`codex_oauth`。
- `auth_kind`: `api_key`、`oauth_pkce`、`oauth_device`、`external_process`。
- `api_key_env_vars`: 多环境变量候选，按优先级解析。
- `base_url_env_var`: 用户覆盖 endpoint。
- `aliases`: slash command 和 config 里的短名。

具体 client 实现 `LLMProvider.stream_chat()`，Agent loop 不直接知道 provider
细节。当前 provider client 已覆盖四类 transport：

- `OpenAIResponsesProvider`: OpenAI Responses API 的流式事件归一化。
- `OpenAIChatProvider`: OpenAI-compatible Chat Completions 的流式 chunk 归一化。
- `AnthropicMessagesProvider`: Anthropic Messages API 的 text/tool_use block 归一化。
- `CodexOAuthProvider`: 通过 `AuthStore` 读取 OpenAI Codex OAuth bearer token，
  再复用 Responses-compatible 流式归一化路径。

Provider 层输出统一为 `StreamEvent`、`ChatResponse` 和 `ToolCall`，这些类型由
`runtime/` 定义并通过 `providers.base` 重新导出。tool schema
在 provider 边界转换为 OpenAI 或 Anthropic 格式。HTTP transport 使用 lazy
`httpx`，单元测试全部注入 fake transport，不触网。

## Runtime Message 设计

Runtime message model 不暴露 provider 原始响应格式：

- `Message`: 支持 `system`、`user`、`assistant`、`tool` 四类 role。
- `ToolCall`: assistant message 上的工具调用，包含稳定 `id`、`name` 和 JSON object 参数。
- `ToolResult`: tool message 上的工具结果，通过 `tool_use_id` 关联 `ToolCall.id`。
- `ChatResponse`: provider 响应聚合结果，可转换为 assistant message。
- `RuntimeEvent`: 流式事件，覆盖 content delta、tool call、tool result、message done 和 error。
- `AgentLoop`: 只依赖 provider-neutral `ChatProvider` 协议，负责 turn lifecycle、
  finalization、tool result 追加、stop signal 和 max-turns 退出。
- `TokenBudget`: 在不引入 provider tokenizer 的前提下提供稳定估算和压缩触发阈值。
- `Compaction`: 保留 system preamble 和最近 N 个 user turn，把更早的 user、
  assistant、tool 和 reasoning metadata 汇总为可解释的 system summary。

消息序列化面向 SQLite session store，保存内部结构而不是 provider raw payload。
AgentLoop 只有在显式配置 `TokenBudget` 时才会在 provider 调用前自动压缩历史；
默认路径保持不压缩，便于测试和迁移旧行为。

## Tool Runtime 设计

工具层和 provider schema 转换分离：

- `ToolSchema`: 面向 provider 的 name、description 和 JSON schema parameters。
- `ToolPermission`: 面向权限/审批层的能力需求，例如 filesystem、network、shell。
- `ToolSpec`: 聚合 schema、权限需求和默认启用状态。
- `Tool`: 执行接口，输入 runtime `ToolCall`，输出统一 `ToolResult`。
- `ToolRegistry`: 负责注册、按 name 查找、enable/disable、导出已启用 schema，
  并实现 AgentLoop 所需的 `run()` 执行网关。

Provider 层只接收 `ToolRegistry.schemas()` 导出的 schema；权限和启停状态留在
tools/runtime 边界，不混进 OpenAI/Anthropic schema。

当前文件工具包括：

- `WorkspacePolicy`: 所有文件路径必须解析到 workspace root 内，阻断 `..` 和
  绝对路径逃逸；`{{file:path:start:end}}` 引用也复用同一策略。
- `FileReadTool`: 支持 1-based range、case-insensitive keyword search、行号输出、
  单行和总输出截断，并在 metadata 中标记截断状态。
- `FilePatchTool`: 只做唯一精确匹配替换；0 次或多次匹配都会返回错误，不猜测位置。
- `FileWriteTool`: 支持 overwrite、append、prepend 和可选创建父目录，写入前展开安全
  file references。
- `ShellTool`: 执行 workspace 内 shell command，支持 timeout、stop signal、stdout
  callback streaming 和危险命令分类；默认危险命令返回 approval-required 错误，只有
  `yolo=True` 时才执行。
- `CodeRunTool`: 只执行临时 Python 脚本，和 shell 命令路径分离；同样约束 cwd 到
  workspace root，并复用 timeout、stop signal、输出截断机制。
- `WebScanTool` / `WebExecuteJsTool`: 保留旧 `web_scan`、`web_execute_js`
  工具名和参数语义，通过 `BrowserBridge` 适配 TMWebDriver/后续 CDP；会话状态由
  `BrowserSessionStore` 独立维护，`execute_js` 结果统一归一化为 `status`、
  `js_return`、`newTabs`、`reloaded`，两个工具都强制输出预算。
- `WebOpenTool`: 新增 `web_open`，可打开 http(s) URL 或把 query 转成搜索 URL
  交给系统浏览器；用于“打开浏览器搜索”这类请求，后续可配合 bridge 工具扫描页面。

浏览器模块分为：

- `browser/cdp_bridge.py`: browser session model、独立 session store、旧
  TMWebDriver adapter、HTTP `/link` bridge 和执行结果归一化；本地 `/link`
  调用会绕过 `http_proxy`/`https_proxy`/`all_proxy`，避免把 `127.0.0.1`
  bridge 请求错误发给外部代理。
- `browser/html_simplifier.py`: 无额外依赖的 HTML 简化器，删除 script/style/hidden/
  floating 噪音节点，保留可操作元素的核心属性，并提供统一截断预算。

## Command 设计

命令使用中心注册表和独立 handler，而不是分散 if/else：

- Session: `/new`、`/clear`、`/history`、`/retry`、`/undo`、`/compact`、`/resume`。
- Configuration: `/model`、`/providers`、`/login`、`/logout`、`/config`、`/env`。
  `openai-codex` 登录支持有头浏览器授权和 `--headless` 无头授权；无头路径只输出
  authorization URL，并可通过 `--callback` 或 `--code` 接收回调凭据，不调用浏览器。
- Tools: `/tools`、`/skills`、`/memory`。
- Info: `/help`、`/commands`、`/doctor`、`/usage`。
- Exit: `/exit`、`/quit`。

`CommandRouter` 负责解析、alias 归一化、未知命令建议和 handler dispatch；
命令可用性通过 `available_commands()` 按 CLI-only、category 等条件过滤。
这个模型后续可直接扩展动态 skill command、命令权限和 feature gates。
当前 CLI bootstrap 已支持 `gae --version`、`gae doctor`、`gae status`、
`gae commands`、`gae chat /status` 等 slash command gateway。交互入口包括
`gae --tui`、`gae tui` 和空参数 `gae chat`；TUI 借鉴 `free-code` 的命令补全、
输入历史和状态提示，以及 `hermes-agent` 的 transcript/status/input 分层，但保持
Python `prompt-toolkit` 实现，复用同一个 `CommandRouter` 和 `CommandContext`。
非 slash 输入会通过 `ChatTurnService` 接入当前 provider 和 `AgentLoop`，成功响应
会写回 runtime message history；`ChatTurnService` 默认注入文件、shell、代码执行
和浏览器工具 schema，并把工具结果交给 `ToolRegistry.run()`。TUI transcript 会显示
`tool>` / `tool<` 行，工具失败会在 `tool< ... error` 后输出压缩后的错误原因；
缺少 API key 或 OAuth token 时返回明确认证错误。`--plain`
强制关闭 Rich 渲染，`--no-animations` 关闭 tool progress 动效。
兼容迁移入口包括 `gae task IODIR --input PROMPT` 和
`gae reflect SCRIPT --once`，用于替换旧 `agentmain.py --task/--reflect`
的文件 I/O 调用方式。

## 状态、Memory 与 Auth

目标状态目录：

```text
~/.generic-agent/
├── agents/
├── auth.json
├── cache/
├── history.jsonl
├── projects/
├── settings.json
├── sessions/
├── skills/
├── state/
│   ├── sessions.sqlite
│   └── checkpoints/
├── tasks/
├── telemetry/
└── transcripts/
```

当前第一版实现 `auth.json` 的原子读写、PKCE helper、loopback callback、
token refresh seam 和 provider token 读取。

Session store 已落地为 `state/session_store.py` + `state/schema.sql`：

- SQLite 文件默认目标为 `$GENERIC_AGENT_CONFIG_DIR/state/sessions.sqlite`
  （默认 `~/.generic-agent/state/sessions.sqlite`，兼容旧 `$GENERIC_AGENT_HOME`）。
- `connect()` 初始化 schema，并对文件数据库启用 WAL 和 foreign keys。
- `sessions` 表保存 session 元数据、provider/model 和 `parent_session_id`。
- `messages` 表按 `(session_id, sequence)` 追加 provider-neutral `Message.to_dict()`。
- `messages_fts` 使用 FTS5 external-content index，通过 trigger 同步搜索内容。
- `branch_session()` 可以创建 parent/child session，并可选择复制父 session 消息。

Memory service 已落地为 `memory/index.py`、`memory/service.py` 和
`skills/crystallizer.py`：

- `MemoryIndex` 读取本地 memory 目录并按 L1/L2/L3/L4 分类；`L1` 对应
  `global_mem_insight.txt`，`L2` 对应 `global_mem.txt`，`L4` 对应
  `L4_raw_sessions/`，其余 SOP/脚本/技能记录归为 `L3`。
- `load_legacy_memory()` 只把旧 `GenericAgent/memory` 作为迁移源，并在缺少
  L1 文件时读取旧 `assets/global_mem_insight_template.txt` 作为索引模板。
- `MemoryService.write_reviewed_entry()` 要求 `approved=True` 和 reviewer
  metadata；L1/L2 追加到全局文件，L3/L4 写入唯一 markdown 文件。
- `SkillCrystallizer` 只把 successful task summary 生成 SOP draft，并在写入前
  用标题、路径和 token similarity 检测 L3 duplicate skill。

checkpoint store 在后续任务中继续实现。

## 测试策略

每个功能任务必须包含至少一个单元测试：

- Provider registry: alias、transport、env resolution。
- Auth: token store、PKCE、refresh 判定、logout。
- Command: registry、alias、category、availability。
- Runtime/State: provider/model switch、message flow、tool dispatch、session store
  create/append/search/branch。
- Memory/Skills: legacy memory migration、L1/L2/L3/L4 classification、reviewed
  writes、SOP draft generation 和 duplicate detection。
- CLI/UI: doctor、commands、slash command parsing、TUI 输入循环、非交互模式。

集成测试只在 feature 完成后加入，不阻塞单元测试快速运行。
