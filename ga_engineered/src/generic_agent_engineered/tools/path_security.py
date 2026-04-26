"""Workspace path safety helpers for filesystem tools."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class PathSecurityError(ValueError):
    """Base path security error."""


class PathOutsideWorkspaceError(PathSecurityError):
    """Raised when a path escapes the configured workspace root."""


class FileReferenceError(ValueError):
    """Raised when a {{file:path:start:end}} reference cannot be expanded."""


@dataclass(frozen=True)
class WorkspacePolicy:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve(strict=True))

    def resolve_path(self, raw_path: str | Path) -> Path:
        if isinstance(raw_path, Path):
            raw = raw_path
        elif isinstance(raw_path, str) and raw_path:
            raw = Path(raw_path)
        else:
            raise PathSecurityError("path is required")

        candidate = raw.expanduser() if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise PathOutsideWorkspaceError(f"path escapes workspace root: {raw_path}")
        return resolved

    def relative_path(self, path: Path) -> str:
        return path.resolve(strict=False).relative_to(self.root).as_posix()


FILE_REFERENCE_PATTERN = re.compile(r"\{\{file:(.+?):(\d+):(\d+)\}\}")


def expand_file_references(content: str, policy: WorkspacePolicy) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_path = match.group(1)
        start = int(match.group(2))
        end = int(match.group(3))
        if start < 1 or end < start:
            raise FileReferenceError(f"invalid file reference range: {start}:{end}")

        path = policy.resolve_path(raw_path)
        if not path.is_file():
            raise FileReferenceError(f"referenced file does not exist: {raw_path}")

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if end > len(lines):
            raise FileReferenceError(
                f"file reference range exceeds file length: {raw_path} has {len(lines)} lines"
            )
        return "".join(lines[start - 1 : end])

    return FILE_REFERENCE_PATTERN.sub(replace, content)
