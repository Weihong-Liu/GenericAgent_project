"""Reviewed memory writes and migration helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .index import MemoryEntry, MemoryIndex, MemoryLayer, load_legacy_memory, slugify


@dataclass(frozen=True)
class MemoryWriteRequest:
    layer: MemoryLayer
    title: str
    content: str
    tags: tuple[str, ...] = ()
    approved: bool = False
    reviewer: str = ""
    source: str = "manual"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryWriteResult:
    entry: MemoryEntry
    path: Path
    created: bool


class MemoryService:
    """High-level memory API with explicit human review gates."""

    def __init__(self, memory_root: Path, *, legacy_root: Path | None = None) -> None:
        self.memory_root = memory_root
        self.legacy_root = legacy_root

    def index(self) -> MemoryIndex:
        return MemoryIndex.from_directory(self.memory_root)

    def load_legacy_index(self, legacy_root: Path | None = None) -> MemoryIndex:
        source = legacy_root or self.legacy_root
        if source is None:
            raise ValueError("legacy_root is required")
        return load_legacy_memory(source)

    def write_reviewed_entry(self, request: MemoryWriteRequest) -> MemoryWriteResult:
        if not request.approved or not request.reviewer.strip():
            raise PermissionError("memory writes require explicit approval and reviewer")
        if not request.title.strip():
            raise ValueError("memory title is required")
        if not request.content.strip():
            raise ValueError("memory content is required")

        path = self._path_for_request(request)
        created = not path.exists()
        rendered = self._render_request(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        if request.layer in {"L1", "L2"}:
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            path.write_text(_append_block(existing, rendered), encoding="utf-8")
        else:
            path.write_text(rendered, encoding="utf-8")

        entry = MemoryEntry(
            layer=request.layer,
            title=request.title,
            content=rendered,
            source_path=path,
            relative_path=path.relative_to(self.memory_root).as_posix(),
            tags=request.tags,
            metadata={
                "reviewer": request.reviewer,
                "source": request.source,
                **request.metadata,
            },
        )
        return MemoryWriteResult(entry=entry, path=path, created=created)

    def _path_for_request(self, request: MemoryWriteRequest) -> Path:
        if request.layer == "L1":
            return self.memory_root / "global_mem_insight.txt"
        if request.layer == "L2":
            return self.memory_root / "global_mem.txt"
        if request.layer == "L4":
            return _unique_path(self.memory_root / "L4_raw_sessions", slugify(request.title))
        return _unique_path(self.memory_root, slugify(request.title))

    def _render_request(self, request: MemoryWriteRequest) -> str:
        content = request.content.strip()
        if request.layer == "L1":
            return content
        if request.layer == "L2":
            return f"## {request.title.strip()}\n{content}\n"
        if content.startswith("#"):
            return f"{content}\n"
        return f"# {request.title.strip()}\n\n{content}\n"


def _unique_path(directory: Path, slug: str) -> Path:
    candidate = directory / f"{slug}.md"
    index = 2
    while candidate.exists():
        candidate = directory / f"{slug}-{index}.md"
        index += 1
    return candidate


def _append_block(existing: str, block: str) -> str:
    prefix = existing.rstrip()
    suffix = block.strip()
    if not prefix:
        return f"{suffix}\n"
    return f"{prefix}\n\n{suffix}\n"
