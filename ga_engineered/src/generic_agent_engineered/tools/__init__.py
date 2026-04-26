"""Tool interfaces and registry."""

from .base import (
    FunctionTool,
    Tool,
    ToolHandler,
    ToolPermission,
    ToolSchema,
    ToolSpec,
    coerce_tool_result,
    tool_error_result,
    validate_tool_name,
)
from .browser import (
    WEB_EXECUTE_JS_SPEC,
    WEB_OPEN_SPEC,
    WEB_SCAN_SPEC,
    WebExecuteJsTool,
    WebOpenTool,
    WebScanTool,
)
from .code_run import CODE_RUN_SPEC, CodeRunTool
from .defaults import build_default_tool_registry
from .file_patch import FILE_PATCH_SPEC, FilePatchTool
from .file_read import FILE_READ_SPEC, FileReadTool
from .file_write import FILE_WRITE_SPEC, FileWriteTool
from .path_security import (
    FileReferenceError,
    PathOutsideWorkspaceError,
    PathSecurityError,
    WorkspacePolicy,
    expand_file_references,
)
from .permissions import (
    CommandRisk,
    ExecutionDecision,
    ExecutionPolicy,
    classify_shell_command,
    decide_execution,
)
from .registry import (
    DisabledToolError,
    DuplicateToolError,
    RegisteredTool,
    ToolRegistry,
    ToolRegistryError,
    UnknownToolError,
)
from .shell import SHELL_SPEC, ShellTool

__all__ = [
    "CODE_RUN_SPEC",
    "CommandRisk",
    "CodeRunTool",
    "DisabledToolError",
    "DuplicateToolError",
    "ExecutionDecision",
    "ExecutionPolicy",
    "FILE_PATCH_SPEC",
    "FILE_READ_SPEC",
    "FILE_WRITE_SPEC",
    "FilePatchTool",
    "FileReadTool",
    "FileReferenceError",
    "FileWriteTool",
    "FunctionTool",
    "PathOutsideWorkspaceError",
    "PathSecurityError",
    "RegisteredTool",
    "SHELL_SPEC",
    "ShellTool",
    "Tool",
    "ToolHandler",
    "ToolPermission",
    "ToolRegistry",
    "ToolRegistryError",
    "ToolSchema",
    "ToolSpec",
    "UnknownToolError",
    "WEB_EXECUTE_JS_SPEC",
    "WEB_OPEN_SPEC",
    "WEB_SCAN_SPEC",
    "WebExecuteJsTool",
    "WebOpenTool",
    "WebScanTool",
    "WorkspacePolicy",
    "build_default_tool_registry",
    "classify_shell_command",
    "coerce_tool_result",
    "decide_execution",
    "expand_file_references",
    "tool_error_result",
    "validate_tool_name",
]
