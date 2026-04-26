"""Layered memory indexing and legacy GenericAgent memory import."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

MemoryLayer = Literal["L1", "L2", "L3", "L4"]

L1_NAMES = {"global_mem_insight.txt"}
L2_NAMES = {"global_mem.txt"}
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_EXTENSIONS = {
    "",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".txt",
    ".yaml",
    ".yml",
}
TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class MemoryEntry:
    layer: MemoryLayer
    title: str
    content: str
    source_path: Path | None = None
    relative_path: str = ""
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)


class MemoryIndex:
    """In-memory searchable index for layered memory entries."""

    def __init__(self, entries: list[MemoryEntry] | tuple[MemoryEntry, ...] = ()) -> None:
        self._entries: list[MemoryEntry] = []
        for entry in entries:
            self.add(entry)

    @classmethod
    def from_directory(cls, root: Path) -> MemoryIndex:
        return cls(load_memory_entries(root))

    @property
    def entries(self) -> tuple[MemoryEntry, ...]:
        return tuple(self._entries)

    def add(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)

    def by_layer(self, layer: MemoryLayer) -> tuple[MemoryEntry, ...]:
        return tuple(entry for entry in self._entries if entry.layer == layer)

    def layer_counts(self) -> dict[MemoryLayer, int]:
        return {
            "L1": len(self.by_layer("L1")),
            "L2": len(self.by_layer("L2")),
            "L3": len(self.by_layer("L3")),
            "L4": len(self.by_layer("L4")),
        }

    def search(
        self,
        query: str,
        *,
        layer: MemoryLayer | None = None,
        limit: int = 20,
    ) -> tuple[MemoryEntry, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        terms = _tokens(query)
        if not terms:
            return ()

        scored: list[tuple[int, str, MemoryEntry]] = []
        for entry in self._entries:
            if layer is not None and entry.layer != layer:
                continue
            haystack = " ".join((entry.title, entry.content, " ".join(entry.tags))).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, entry.title.lower(), entry))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return tuple(entry for _, _, entry in scored[:limit])

    def find_duplicate(self, entry: MemoryEntry) -> MemoryEntry | None:
        for existing in self._entries:
            if existing.content_hash == entry.content_hash:
                return existing
            if existing.normalized_title and existing.normalized_title == entry.normalized_title:
                return existing
            if existing.relative_path and existing.relative_path == entry.relative_path:
                return existing
        return None


def load_legacy_memory(source_root: Path) -> MemoryIndex:
    """Load legacy GenericAgent memory as a migration source."""
    root = _legacy_memory_root(source_root)
    project_root = _legacy_project_root(source_root, root)
    entries = load_memory_entries(root)

    assets = project_root / "assets"
    if not any(entry.layer == "L1" for entry in entries):
        template = assets / "global_mem_insight_template.txt"
        if template.exists():
            entries.append(_entry_from_file(template, layer="L1", base=project_root))
    if not any(entry.layer == "L2" for entry in entries):
        global_memory = root / "global_mem.txt"
        if global_memory.exists():
            entries.append(_entry_from_file(global_memory, layer="L2", base=root))
    return MemoryIndex(entries)


def load_memory_entries(root: Path) -> list[MemoryEntry]:
    if not root.exists():
        return []
    if root.is_file():
        return [_entry_from_file(root, layer=classify_memory_path(root), base=root.parent)]

    entries: list[MemoryEntry] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _should_skip(path, root):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        entries.append(_entry_from_file(path, layer=classify_memory_path(path), base=root))
    return entries


def classify_memory_path(path: Path) -> MemoryLayer:
    normalized_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    if name in L1_NAMES:
        return "L1"
    if name in L2_NAMES:
        return "L2"
    if "l4_raw_sessions" in normalized_parts:
        return "L4"
    return "L3"


def normalize_title(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.removesuffix(".md").removesuffix(".py").removesuffix(".txt")
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\bsop\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def slugify(value: str) -> str:
    normalized = normalize_title(value)
    slug = SLUG_RE.sub("-", normalized).strip("-")
    return slug or "memory-entry"


def _entry_from_file(path: Path, *, layer: MemoryLayer, base: Path) -> MemoryEntry:
    content = path.read_text(encoding="utf-8", errors="replace")
    relative_path = _relative_path(path, base)
    title = _title_from_content(content) or _title_from_path(path)
    tags = _tags_for_path(path, layer)
    return MemoryEntry(
        layer=layer,
        title=title,
        content=content,
        source_path=path,
        relative_path=relative_path,
        tags=tags,
        metadata={"source": "legacy" if "GenericAgent" in path.parts else "memory"},
    )


def _legacy_memory_root(source_root: Path) -> Path:
    source = source_root.expanduser().resolve()
    memory_dir = source / "memory"
    if memory_dir.exists():
        return memory_dir
    return source


def _legacy_project_root(source_root: Path, memory_root: Path) -> Path:
    source = source_root.expanduser().resolve()
    if memory_root.name == "memory":
        return memory_root.parent
    return source


def _should_skip(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in SKIP_DIRS or part.startswith(".") for part in relative_parts)


def _relative_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _title_from_content(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _title_from_path(path: Path) -> str:
    if path.name == "SKILL.md":
        return path.parent.name
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def _tags_for_path(path: Path, layer: MemoryLayer) -> tuple[str, ...]:
    tags = [layer.lower()]
    name = path.name.lower()
    if name.endswith("_sop.md") or "sop" in name:
        tags.append("sop")
    if path.suffix.lower() == ".py":
        tags.append("tool")
    if path.name == "SKILL.md":
        tags.append("skill")
    return tuple(dict.fromkeys(tags))


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_RE.findall(value))
