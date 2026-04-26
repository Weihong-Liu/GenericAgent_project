# Advanced TUI Redesign Plan

## 目标

把当前 prompt-toolkit/plain TUI 升级为接近 `hermes-agent` 和 `free-code` 体验的
高级终端界面，同时保持 Python runtime 是唯一 Agent 后端。

核心要求：

- `GenericAgent` 或 `ga` 直接进入 TUI；`gae` 也改为默认进入 TUI。
- TUI 启动时自动创建 Python interactive backend。
- 界面能实时看到 assistant 输出、工具调用、命令执行、shell/code 输出、错误和耗时。
- 欢迎页包含 GenericAgent 品牌 ASCII logo、紧凑徽标、当前 provider/model/session/config 状态。
- 保持当前 slash command、provider、tools、settings、session/memory 架构，不把业务逻辑搬到 UI。
- 预留 TypeScript/Ink 前端可能性，但不作为第一阶段默认实现。

## 技术路线决策

### 方案 A：Python Textual TUI（主线）

使用 `Textual` 重做主界面，Python 进程内直接连接 `InteractiveBackend`。

优点：

- 和当前 Python runtime、provider、tool registry、config/session/auth 直接集成。
- 可以做真正的布局、滚动面板、输入框、命令面板、状态栏和实时事件渲染。
- 测试可以用 Textual pilot + mock backend 覆盖。
- 不引入 Node/TS 工程复杂度，继续以 `uv` 管理。

代价：

- 新增 Python UI 依赖。
- 需要把当前 `ui/tui.py` 的 prompt loop 抽到可回退路径。

### 方案 B：TypeScript/Ink TUI（后续可选）

使用 TS/Ink 作为前端，启动时 spawn：

```bash
gae runtime serve --stdio
```

TS 只通过 JSON Lines 协议和 Python 后端通信。

优点：

- React 组件模型适合复杂终端 UI。
- 长期可以更接近 free-code 的 TS 交互方式。

代价：

- 引入 `node/pnpm/tsup/vitest` 等第二套工程链路。
- Python/TS 协议、发布、测试和调试复杂度明显上升。
- 如果过早使用，会拖慢当前 Python 工程化主线。

### ADR

Decision: M7 先采用 Python Textual 实现高级 TUI，同时先抽象 runtime event protocol。

Drivers:

- 当前 GenericAgent 工程主体是 Python，runtime/tool/session/auth 都已在 Python。
- 用户当前痛点是 TUI 丑、交互不可视，而不是必须 React/TS。
- 实时工具事件需要直接接入 `AgentLoop`、`ToolRegistry` 和 shell streaming。
- 未来 TS TUI 需要稳定协议，协议先于 TS 前端更合理。

Alternatives considered:

- 继续 `prompt_toolkit + rich`: 改动小，但复杂布局和实时事件面板会变得脆弱。
- 立即 TS/Ink: UI 能力强，但会引入双语言工程和协议成本。

Why chosen:

Textual 能最快把界面做成高级 TUI，并且不会复制后端逻辑。通过 `gae runtime serve --stdio`
保留 TS 前端接口，等 Python TUI 和协议稳定后再决定是否正式做 TS。

Consequences:

- M7 会新增 Textual 依赖和一组 UI widget。
- 旧 prompt-toolkit TUI 保留为 fallback。
- M8 的 TS/Ink 只做 spike，除非后续明确批准，不进入默认路径。

## 目标界面

### 桌面宽屏布局

```text
┌──────────────── GenericAgent ─ provider/model/session/status ────────────────┐
│ Welcome / compact status panel │ Transcript: user / assistant / tools         │
│ commands, config, auth, tools  │ tool timeline cards + command/process logs   │
├────────────────────────────────┴──────────────────────────────────────────────┤
│ ga> input box with slash completion, history, multiline paste, interrupt      │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 窄终端布局

```text
GenericAgent status bar
Transcript
Tool/process events inline
Input
```

### 欢迎页草案

全宽 logo 参考 hermes-agent 的 Rich markup，但品牌必须是 GenericAgent：

```python
GENERIC_AGENT_LOGO = """[bold #FFD700] ██████╗ ███████╗███╗   ██╗███████╗██████╗ ██╗ ██████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗[/]
[bold #FFD700]██╔════╝ ██╔════╝████╗  ██║██╔════╝██╔══██╗██║██╔════╝     ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝[/]
[#FFBF00]██║  ███╗█████╗  ██╔██╗ ██║█████╗  ██████╔╝██║██║          ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║[/]
[#FFBF00]██║   ██║██╔══╝  ██║╚██╗██║██╔══╝  ██╔══██╗██║██║          ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║[/]
[#CD7F32]╚██████╔╝███████╗██║ ╚████║███████╗██║  ██║██║╚██████╗     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║[/]
[#CD7F32] ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝[/]"""
```

紧凑徽标不直接复制 Hermes Caduceus，改为 GenericAgent 专属 emblem：

```python
GENERIC_AGENT_EMBLEM = """[#CD7F32]      ╭────────────╮[/]
[#FFBF00]      │  GA  CORE  │[/]
[#FFD700]  ╭───┤  TOOLS     ├───╮[/]
[#FFD700]  │   │  MEMORY    │   │[/]
[#FFBF00]  ╰───┤  RUNTIME   ├───╯[/]
[#CD7F32]      ╰────────────╯[/]"""
```

## Runtime Event Protocol

Textual TUI 和未来 TS TUI 都消费统一事件：

```json
{"event":"session.started","session_id":"default","provider":"anthropic","model":"glm-5.1"}
{"event":"user.message","text":"你好"}
{"event":"assistant.delta","text":"你好"}
{"event":"tool.call","id":"call_1","name":"web_scan","args":{"text_only":true}}
{"event":"tool.output","id":"call_1","chunk":"..."}
{"event":"tool.result","id":"call_1","ok":true,"elapsed_ms":830,"summary":"tabs=1 chars=4200"}
{"event":"command.result","command":"/tools","ok":true,"content":"..."}
{"event":"process.output","tool":"shell","stream":"stdout","chunk":"..."}
{"event":"error","source":"browser_bridge","message":"connection refused on 127.0.0.1:18766/link"}
```

输入请求：

```json
{"id":"1","method":"chat.send","params":{"text":"你好"}}
{"id":"2","method":"command.run","params":{"line":"/tools"}}
{"id":"3","method":"runtime.interrupt","params":{}}
```

## 开发任务

1. `GAE-023`：完成本计划和任务索引。
2. `GAE-024`：抽象 `InteractiveBackend` 和 JSON Lines runtime protocol。
3. `GAE-025`：实现 Textual 主界面和核心 widget。
4. `GAE-026`：添加 `ga` / `GenericAgent` console scripts，并让空参数默认进 TUI。
5. `GAE-027`：实现 free-code 风格工具/命令/process 实时渲染。
6. `GAE-028`：实现 hermes-agent 风格欢迎页和主题系统。
7. `GAE-029`：补齐测试、文档、报告和 release notes。
8. `GAE-030`：可选 TS/Ink spike，只在 Python protocol 稳定后执行。

## 开发流程

每个任务按之前流程执行：

- 先补或更新对应单元测试。
- 小步实现，不把 provider/tool/session 业务逻辑放进 UI widget。
- 每个任务更新 `tasks/TASK_REPORT.md`，必要时更新 README/架构文档/changelog。
- 每个任务完成后跑：

```bash
python3 -m json.tool tasks.json
python3 -m compileall -q src tests
python3 -m unittest discover -s tests
UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync pytest
UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync ruff check .
UV_CACHE_DIR=/tmp/ga-engineered-uv-cache uv run --no-sync mypy src
git diff --check
```

- 每个任务完成后按 Lore Commit Protocol 提交。

## 风险与缓解

- Textual 依赖缺失：保留当前 prompt-toolkit/plain TUI fallback。
- 实时输出刷屏：所有 tool/process 输出默认分块、折叠、限长。
- TS 前端过早复杂化：M8 只做 P2 spike，默认不进入发布路径。
- 终端宽度不足：logo 和布局必须有 compact fallback。
- 后端协议膨胀：M7 只覆盖 chat、command、tool、process、status、error 六类事件。
