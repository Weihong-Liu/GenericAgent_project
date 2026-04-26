"""Browser tools backed by a replaceable bridge."""

from __future__ import annotations

import json
import urllib.parse
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generic_agent_engineered.browser import (
    BrowserBridge,
    BrowserExecution,
    BrowserSessionError,
    BrowserSessionStore,
    normalize_execute_result,
    simplify_html,
    truncate_with_budget,
)
from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import PathSecurityError, WorkspacePolicy

WEB_SCAN_SCRIPT = (
    "return document.documentElement ? document.documentElement.outerHTML : "
    "(document.body ? document.body.innerHTML : '');"
)
WEB_SCAN_TEXT_SCRIPT = "return document.body ? document.body.innerText : '';"


WEB_OPEN_SPEC = ToolSpec(
    schema=ToolSchema(
        name="web_open",
        description=(
            "Open an http(s) URL or a search query in the system browser. "
            "Use this before web_scan when the user asks to open/search the web. "
            "This only opens a tab; it does not prove the page content was read."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute http(s) URL to open.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query to open when url is not provided.",
                },
                "search_engine": {
                    "type": "string",
                    "description": "Search engine URL prefix for query searches.",
                    "default": "https://www.bing.com/search?q=",
                },
            },
        },
    ),
    permissions=(ToolPermission("browser:open", "open URLs in the system browser"),),
)


WEB_SCAN_SPEC = ToolSpec(
    schema=ToolSchema(
        name="web_scan",
        description=(
            "Get simplified HTML/text and browser tab metadata from the active session. "
            "If the result is an error or has no content field, do not infer page contents."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tabs_only": {
                    "type": "boolean",
                    "description": "Return tab list only without scanning page content.",
                    "default": False,
                },
                "switch_tab_id": {
                    "type": "string",
                    "description": "Optional tab/session id to make active before scanning.",
                },
                "text_only": {
                    "type": "boolean",
                    "description": "Return plain visible text instead of simplified HTML.",
                    "default": False,
                },
                "timeout": {
                    "type": "number",
                    "description": "JavaScript execution timeout in seconds.",
                    "default": 15,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Output character budget, capped by tool policy.",
                    "default": 35000,
                },
            },
        },
    ),
    permissions=(ToolPermission("browser:read", "read browser tab metadata and page content"),),
)


WEB_EXECUTE_JS_SPEC = ToolSpec(
    schema=ToolSchema(
        name="web_execute_js",
        description="Execute JavaScript in a browser tab and normalize TMWebDriver-style results.",
        parameters={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript source to execute."},
                "switch_tab_id": {
                    "type": "string",
                    "description": "Optional tab/session id to make active before execution.",
                },
                "no_monitor": {
                    "type": "boolean",
                    "description": "Compatibility flag; monitoring is deferred to the bridge.",
                    "default": False,
                },
                "timeout": {
                    "type": "number",
                    "description": "JavaScript execution timeout in seconds.",
                    "default": 15,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "JavaScript return value budget, capped by tool policy.",
                    "default": 8000,
                },
                "save_to_file": {
                    "type": "string",
                    "description": "Optional workspace-relative path for the full JS return value.",
                },
            },
            "required": ["script"],
        },
    ),
    permissions=(ToolPermission("browser:execute_js", "execute JavaScript in browser tabs"),),
)


@dataclass
class WebOpenTool:
    open_browser: Callable[[str], bool] = webbrowser.open
    default_search_engine: str = "https://www.bing.com/search?q="

    @property
    def spec(self) -> ToolSpec:
        return WEB_OPEN_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            target = _target_url(
                url=_optional_str(tool_call.arguments.get("url")),
                query=_optional_str(tool_call.arguments.get("query")),
                search_engine=_optional_str(tool_call.arguments.get("search_engine"))
                or self.default_search_engine,
            )
            opened = self.open_browser(target)
            return ToolResult(
                tool_use_id=tool_call.id,
                content=_json({"status": "success", "url": target, "opened": opened}),
                metadata={"url": target, "opened": opened},
            )
        except (ValueError, TypeError) as exc:
            return _error_result(tool_call, str(exc), {"error": exc.__class__.__name__})


@dataclass
class WebScanTool:
    bridge: BrowserBridge
    session_store: BrowserSessionStore = field(default_factory=BrowserSessionStore)
    default_timeout: float = 15.0
    max_timeout: float = 60.0
    default_output_chars: int = 35_000
    max_output_chars: int = 80_000

    @property
    def spec(self) -> ToolSpec:
        return WEB_SCAN_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            sessions = self.session_store.refresh(tuple(self.bridge.list_sessions()))
            if not sessions:
                return _error_result(tool_call, "没有可用的浏览器标签页", {"tabs_count": 0})

            switch_tab_id = _optional_str(tool_call.arguments.get("switch_tab_id"))
            if switch_tab_id:
                self.session_store.select(switch_tab_id)
            active_session = self.session_store.active()
            tabs_only = _bool_arg(tool_call.arguments.get("tabs_only", False), "tabs_only")
            text_only = _bool_arg(tool_call.arguments.get("text_only", False), "text_only")
            timeout = _timeout_seconds(
                tool_call.arguments.get("timeout", self.default_timeout),
                max_timeout=self.max_timeout,
            )
            max_chars = _output_budget(
                tool_call.arguments.get("max_chars", self.default_output_chars),
                max_output_chars=self.max_output_chars,
            )
            metadata = self._metadata(max_chars=max_chars, text_only=text_only)
            payload: dict[str, Any] = {"status": "success", "metadata": metadata["browser"]}

            if tabs_only:
                return ToolResult(
                    tool_use_id=tool_call.id,
                    content=_json(payload),
                    metadata=metadata,
                )

            raw_result = self.bridge.execute_js(
                WEB_SCAN_TEXT_SCRIPT if text_only else WEB_SCAN_SCRIPT,
                session_id=active_session.id,
                timeout=timeout,
            )
            execution = normalize_execute_result(raw_result)
            if not execution.successful:
                payload = execution.to_payload()
                payload["metadata"] = metadata["browser"]
                return ToolResult(
                    tool_use_id=tool_call.id,
                    content=_json(payload),
                    is_error=True,
                    metadata=metadata,
                )

            simplified = simplify_html(
                _stringify_for_page(execution.js_return),
                text_only=text_only,
                max_chars=max_chars,
            )
            metadata.update(
                {
                    "original_chars": simplified.original_chars,
                    "simplified_chars": simplified.simplified_chars,
                    "truncated": simplified.truncated,
                }
            )
            payload["content"] = simplified.content
            return ToolResult(
                tool_use_id=tool_call.id,
                content=_json(payload),
                metadata=metadata,
            )
        except (BrowserSessionError, OSError, ValueError, TypeError) as exc:
            return _error_result(tool_call, str(exc), {"error": exc.__class__.__name__})

    def _metadata(self, *, max_chars: int, text_only: bool) -> dict[str, Any]:
        tabs = self.session_store.to_tabs()
        browser = {
            "tabs_count": len(tabs),
            "tabs": tabs,
            "active_tab": self.session_store.active_session_id,
        }
        return {
            "browser": browser,
            "max_chars": max_chars,
            "text_only": text_only,
        }


@dataclass
class WebExecuteJsTool:
    bridge: BrowserBridge
    session_store: BrowserSessionStore = field(default_factory=BrowserSessionStore)
    workspace_root: Path | None = None
    default_timeout: float = 15.0
    max_timeout: float = 60.0
    default_output_chars: int = 8_000
    max_output_chars: int = 80_000

    @property
    def spec(self) -> ToolSpec:
        return WEB_EXECUTE_JS_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            script = _required_str(tool_call.arguments, "script")
            sessions = self.session_store.refresh(tuple(self.bridge.list_sessions()))
            if not sessions:
                return _error_result(tool_call, "没有可用的浏览器标签页", {"tabs_count": 0})

            switch_tab_id = _optional_str(tool_call.arguments.get("switch_tab_id"))
            if switch_tab_id:
                self.session_store.select(switch_tab_id)
            active_session = self.session_store.active()
            timeout = _timeout_seconds(
                tool_call.arguments.get("timeout", self.default_timeout),
                max_timeout=self.max_timeout,
            )
            max_chars = _output_budget(
                tool_call.arguments.get("max_chars", self.default_output_chars),
                max_output_chars=self.max_output_chars,
            )
            raw_result = self.bridge.execute_js(
                script,
                session_id=active_session.id,
                timeout=timeout,
            )
            execution = normalize_execute_result(raw_result)
            payload, truncated = _budget_execution(execution, max_chars=max_chars)
            payload["tab_id"] = active_session.id
            payload["no_monitor"] = _bool_arg(
                tool_call.arguments.get("no_monitor", False),
                "no_monitor",
            )
            save_to_file = _optional_str(tool_call.arguments.get("save_to_file"))
            if save_to_file:
                payload.update(self._save_js_return(save_to_file, execution.js_return))

            metadata = {
                "active_tab": active_session.id,
                "max_chars": max_chars,
                "truncated": truncated,
                "new_tabs": len(execution.new_tabs),
                "reloaded": execution.reloaded,
            }
            return ToolResult(
                tool_use_id=tool_call.id,
                content=_json(payload),
                is_error=not execution.successful,
                metadata=metadata,
            )
        except (BrowserSessionError, OSError, PathSecurityError, ValueError, TypeError) as exc:
            return _error_result(tool_call, str(exc), {"error": exc.__class__.__name__})

    def _save_js_return(self, raw_path: str, value: Any) -> dict[str, Any]:
        if self.workspace_root is None:
            return {"save_error": "workspace root is not configured"}
        policy = WorkspacePolicy(self.workspace_root)
        path = policy.resolve_path(raw_path)
        if not path.parent.is_dir():
            raise FileNotFoundError(f"parent directory does not exist: {path.parent}")
        path.write_text(_stringify_for_file(value), encoding="utf-8")
        return {"saved_to_file": policy.relative_path(path)}


def _budget_execution(
    execution: BrowserExecution,
    *,
    max_chars: int,
) -> tuple[dict[str, Any], bool]:
    payload = execution.to_payload()
    rendered = _stringify_for_file(execution.js_return)
    budgeted, truncated = truncate_with_budget(rendered, max_chars)
    if truncated:
        payload["js_return"] = budgeted
    return payload, truncated


def _error_result(tool_call: ToolCall, message: str, metadata: dict[str, Any]) -> ToolResult:
    payload = {"status": "error", "error": message}
    return ToolResult(
        tool_use_id=tool_call.id,
        content=_json(payload),
        is_error=True,
        metadata=metadata,
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _target_url(*, url: str | None, query: str | None, search_engine: str) -> str:
    if url:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        return url
    if query:
        parsed_engine = urllib.parse.urlparse(search_engine)
        if parsed_engine.scheme not in {"http", "https"} or not parsed_engine.netloc:
            raise ValueError("search_engine must be an absolute http(s) URL prefix")
        return f"{search_engine}{urllib.parse.quote_plus(query)}"
    raise ValueError("web_open requires either url or query")


def _stringify_for_page(value: Any) -> str:
    if isinstance(value, str):
        return value
    return _json(value)


def _stringify_for_file(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    raise TypeError("optional browser ids and paths must be strings")


def _bool_arg(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError(f"{name} must be a boolean")


def _timeout_seconds(value: Any, *, max_timeout: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("timeout must be a number")
    if value <= 0:
        raise ValueError("timeout must be positive")
    return min(float(value), max_timeout)


def _output_budget(value: Any, *, max_output_chars: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("max_chars must be an integer")
    if value < 1:
        raise ValueError("max_chars must be positive")
    return min(value, max_output_chars)
