"""Default tool registry for interactive chat."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from generic_agent_engineered.browser import BrowserBridge, BrowserSessionStore, CdpBridge
from generic_agent_engineered.engine import AgentRuntime

from .base import Tool
from .browser import WebExecuteJsTool, WebOpenTool, WebScanTool
from .code_run import CodeRunTool
from .file_patch import FilePatchTool
from .file_read import FileReadTool
from .file_write import FileWriteTool
from .registry import ToolRegistry
from .shell import ShellTool


def build_default_tool_registry(
    runtime: AgentRuntime,
    *,
    workspace_root: Path | None = None,
    browser_bridge: BrowserBridge | None = None,
    open_browser: Callable[[str], bool] | None = None,
) -> ToolRegistry:
    root = (workspace_root or Path.cwd()).resolve()
    bridge = browser_bridge or CdpBridge()
    browser_sessions = BrowserSessionStore()
    tools: list[Tool] = [
        FileReadTool(root),
        FileWriteTool(root),
        FilePatchTool(root),
        CodeRunTool(root),
        ShellTool(root, yolo=runtime.settings.yolo),
        WebOpenTool() if open_browser is None else WebOpenTool(open_browser=open_browser),
        WebScanTool(bridge, session_store=browser_sessions),
        WebExecuteJsTool(bridge, session_store=browser_sessions, workspace_root=root),
    ]
    return ToolRegistry(tools)
