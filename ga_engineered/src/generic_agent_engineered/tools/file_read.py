"""Workspace-constrained file read tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import PathSecurityError, WorkspacePolicy

FILE_READ_SPEC = ToolSpec(
    schema=ToolSchema(
        name="file_read",
        description=(
            "Read a UTF-8 text file from the workspace with optional range or keyword search."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "start": {
                    "type": "integer",
                    "description": "1-based start line",
                    "default": 1,
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum lines to return",
                    "default": 200,
                },
                "keyword": {
                    "type": "string",
                    "description": "Optional case-insensitive keyword search",
                },
                "show_linenos": {
                    "type": "boolean",
                    "description": "Prefix returned lines with line numbers",
                    "default": True,
                },
            },
            "required": ["path"],
        },
    ),
    permissions=(ToolPermission("filesystem:read", "read workspace files"),),
)


@dataclass
class FileReadTool:
    workspace_root: Path
    default_count: int = 200
    max_count: int = 1000
    max_line_chars: int = 8000
    max_result_chars: int = 120_000

    @property
    def spec(self) -> ToolSpec:
        return FILE_READ_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            policy = WorkspacePolicy(self.workspace_root)
            path = policy.resolve_path(_required_str(tool_call.arguments, "path"))
            start = _positive_int(tool_call.arguments.get("start", 1), "start")
            requested_count = _positive_int(
                tool_call.arguments.get("count", self.default_count),
                "count",
            )
            count = min(requested_count, self.max_count)
            keyword = _optional_str(tool_call.arguments.get("keyword"))
            show_linenos = _bool_arg(tool_call.arguments.get("show_linenos", True))
            content, metadata = self._read(
                path,
                policy=policy,
                start=start,
                count=count,
                keyword=keyword,
                show_linenos=show_linenos,
            )
            if requested_count > self.max_count:
                metadata["requested_count"] = requested_count
                metadata["count_capped"] = True
            return ToolResult(tool_use_id=tool_call.id, content=content, metadata=metadata)
        except (OSError, PathSecurityError, ValueError, TypeError) as exc:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=str(exc),
                is_error=True,
                metadata={"error": exc.__class__.__name__},
            )

    def _read(
        self,
        path: Path,
        *,
        policy: WorkspacePolicy,
        start: int,
        count: int,
        keyword: str | None,
        show_linenos: bool,
    ) -> tuple[str, dict[str, Any]]:
        if not path.is_file():
            raise FileNotFoundError(f"file not found: {policy.relative_path(path)}")

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines = len(lines)
        selected_start = start
        note = ""

        if keyword:
            match_index = _find_keyword(lines, keyword, start=start)
            if match_index is None:
                note = f"Keyword '{keyword}' not found after line {start}; showing requested range."
            else:
                before = max(0, count // 3)
                selected_start = max(start, match_index + 1 - before)

        start_index = max(0, selected_start - 1)
        selected = list(enumerate(lines[start_index : start_index + count], start=selected_start))
        rendered_lines: list[str] = []
        truncated = False
        for number, line in selected:
            rendered_line = line
            if len(rendered_line) > self.max_line_chars:
                rendered_line = f"{rendered_line[: self.max_line_chars].rstrip()} ... [TRUNCATED]"
                truncated = True
            rendered_lines.append(f"{number}|{rendered_line}" if show_linenos else rendered_line)

        body = "\n".join(rendered_lines)
        if note:
            body = f"{note}\n\n{body}" if body else note
        header = (
            f"[FILE] {policy.relative_path(path)} total_lines={total_lines} "
            f"returned_lines={len(selected)}"
        )
        content = f"{header}\n{body}" if show_linenos else body
        if len(content) > self.max_result_chars:
            content = f"{content[: self.max_result_chars].rstrip()}\n... [TRUNCATED]"
            truncated = True

        return content, {
            "path": policy.relative_path(path),
            "total_lines": total_lines,
            "start": selected_start,
            "returned_lines": len(selected),
            "truncated": truncated,
            "keyword": keyword or "",
        }


def _find_keyword(lines: list[str], keyword: str, *, start: int) -> int | None:
    needle = keyword.lower()
    for index, line in enumerate(lines[max(0, start - 1) :], start=max(0, start - 1)):
        if needle in line.lower():
            return index
    return None


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
    raise TypeError("keyword must be a string")


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


def _bool_arg(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError("show_linenos must be a boolean")
