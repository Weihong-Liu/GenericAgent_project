"""Workspace-constrained exact text patch tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult

from .base import ToolPermission, ToolSchema, ToolSpec
from .path_security import (
    FileReferenceError,
    PathSecurityError,
    WorkspacePolicy,
    expand_file_references,
)

FILE_PATCH_SPEC = ToolSpec(
    schema=ToolSchema(
        name="file_patch",
        description="Replace one unique exact text block in a workspace file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative file path"},
                "old_content": {
                    "type": "string",
                    "description": "Existing text block; must match exactly once",
                },
                "new_content": {
                    "type": "string",
                    "description": "Replacement text. Supports {{file:path:start:end}} references.",
                },
            },
            "required": ["path", "old_content", "new_content"],
        },
    ),
    permissions=(
        ToolPermission("filesystem:read", "read target file before patching"),
        ToolPermission("filesystem:write", "write patched workspace file"),
    ),
)


@dataclass
class FilePatchTool:
    workspace_root: Path

    @property
    def spec(self) -> ToolSpec:
        return FILE_PATCH_SPEC

    async def run(self, tool_call: ToolCall) -> ToolResult:
        try:
            policy = WorkspacePolicy(self.workspace_root)
            path = policy.resolve_path(_required_str(tool_call.arguments, "path"))
            old_content = _required_str(tool_call.arguments, "old_content")
            new_content = expand_file_references(
                _required_str(tool_call.arguments, "new_content"),
                policy,
            )
            if old_content == "":
                raise ValueError("old_content must not be empty")
            if not path.is_file():
                raise FileNotFoundError(f"file not found: {policy.relative_path(path)}")

            original = path.read_text(encoding="utf-8", errors="replace")
            match_count = original.count(old_content)
            if match_count == 0:
                raise ValueError(
                    "old_content was not found; read the file again and provide exact text"
                )
            if match_count > 1:
                raise ValueError(
                    f"old_content matched {match_count} times; provide a unique text block"
                )

            updated = original.replace(old_content, new_content, 1)
            path.write_text(updated, encoding="utf-8")
            return ToolResult(
                tool_use_id=tool_call.id,
                content=f"file_patch success: {policy.relative_path(path)}",
                metadata={
                    "path": policy.relative_path(path),
                    "replacements": 1,
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
