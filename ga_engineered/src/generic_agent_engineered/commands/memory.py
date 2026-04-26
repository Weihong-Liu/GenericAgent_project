"""Memory slash command handlers."""

from __future__ import annotations

from pathlib import Path

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand


def handle_memory(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    action = parsed.argv[0] if parsed.argv else "show"
    memory_dir = context.runtime.settings.home / "memory"
    if action == "show":
        return _show_memory(memory_dir)
    if action == "search":
        query = " ".join(parsed.argv[1:]).strip()
        return _search_memory(memory_dir, query)
    if action == "edit":
        target = parsed.argv[1] if len(parsed.argv) > 1 else "memory.md"
        return CommandResult(
            f"Memory edit target: {memory_dir / target}",
            metadata={"path": str(memory_dir / target)},
        )
    return CommandResult(f"unknown /memory action: {action}", is_error=True)


def _show_memory(memory_dir: Path) -> CommandResult:
    if not memory_dir.exists():
        return CommandResult(f"No memory directory yet: {memory_dir}", metadata={"count": 0})
    files = sorted(path for path in memory_dir.rglob("*") if path.is_file())
    if not files:
        return CommandResult(f"Memory directory is empty: {memory_dir}", metadata={"count": 0})
    lines = ["Memory files"]
    lines.extend(f"  {path.relative_to(memory_dir)}" for path in files)
    return CommandResult("\n".join(lines), metadata={"count": len(files)})


def _search_memory(memory_dir: Path, query: str) -> CommandResult:
    if not query:
        return CommandResult("/memory search requires a query", is_error=True)
    if not memory_dir.exists():
        return CommandResult(f"No memory directory yet: {memory_dir}", metadata={"matches": 0})

    matches: list[str] = []
    needle = query.lower()
    for path in sorted(memory_dir.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if needle in text.lower():
            matches.append(str(path.relative_to(memory_dir)))
    if not matches:
        return CommandResult(f"No memory matches for: {query}", metadata={"matches": 0})
    return CommandResult(
        "Memory matches\n" + "\n".join(f"  {match}" for match in matches),
        metadata={"matches": len(matches)},
    )


MEMORY_HANDLERS: dict[str, CommandHandler] = {
    "memory": handle_memory,
}
