"""Workspace-constrained file write tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import (
    FileReferenceError,
    PathSecurityError,
    WorkspacePolicy,
    expand_file_references,
)

WriteMode = Literal["overwrite", "append", "prepend"]


FILE_WRITE_SPEC = ToolSpec(
    schema=ToolSchema(
        name="file_write",
        description="Create, overwrite, append, or prepend UTF-8 text inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "content": {"type": "string", "description": "Text content to write"},
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append", "prepend"],
                    "description": "Write mode",
                    "default": "overwrite",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create missing parent directories",
                    "default": False,
                },
            },
            "required": ["path", "content"],
        },
    ),
    permissions=(ToolPermission("filesystem:write", "write workspace files"),),
)


@dataclass
class FileWriteTool:
    workspace_root: Path

    @property
    def spec(self) -> ToolSpec:
        return FILE_WRITE_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            policy = WorkspacePolicy(self.workspace_root)
            path = policy.resolve_path(_required_str(tool_call.arguments, "path"))
            content = expand_file_references(_required_str(tool_call.arguments, "content"), policy)
            mode = _write_mode(tool_call.arguments.get("mode", "overwrite"))
            create_dirs = _bool_arg(tool_call.arguments.get("create_dirs", False), "create_dirs")
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            if not path.parent.is_dir():
                raise FileNotFoundError(f"parent directory does not exist: {path.parent}")

            original = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
            if mode == "overwrite":
                updated = content
            elif mode == "append":
                updated = f"{original}{content}"
            else:
                updated = f"{content}{original}"

            path.write_text(updated, encoding="utf-8")
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"file_write success: {policy.relative_path(path)}",
                metadata={
                    "path": policy.relative_path(path),
                    "mode": mode,
                    "bytes_written": len(updated.encode("utf-8")),
                },
            )
        except (OSError, PathSecurityError, FileReferenceError, ValueError, TypeError) as exc:
            return ToolResult(
                tool_use_id=tool_call.id,
                content=str(exc),
                is_error=True,
                metadata={"error": exc.__class__.__name__},
            )


def _required_str(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is required")
    return value


def _write_mode(value: Any) -> WriteMode:
    if value in {"overwrite", "append", "prepend"}:
        return cast(WriteMode, value)
    raise ValueError("mode must be one of: overwrite, append, prepend")


def _bool_arg(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError(f"{name} must be a boolean")
