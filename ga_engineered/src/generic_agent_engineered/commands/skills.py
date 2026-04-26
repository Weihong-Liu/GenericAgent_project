"""Skill slash command handlers."""

from __future__ import annotations

from pathlib import Path

from .base import CommandContext, CommandHandler, CommandResult, ParsedCommand


def handle_skills(context: CommandContext, parsed: ParsedCommand) -> CommandResult:
    action = parsed.argv[0] if parsed.argv else "list"
    roots = _skill_roots(context)
    skills = _discover_skills(roots)
    if action == "list":
        return _render_skills(skills)
    if action == "search":
        query = " ".join(parsed.argv[1:]).strip().lower()
        if not query:
            return CommandResult("/skills search requires a query", is_error=True)
        return _render_skills([item for item in skills if query in item[0].lower()])
    if action == "inspect":
        if len(parsed.argv) < 2:
            return CommandResult("/skills inspect requires a skill name", is_error=True)
        return _inspect_skill(skills, parsed.argv[1])
    if action == "reload":
        return CommandResult(f"Skill cache reload requested for {len(skills)} discovered skill(s)")
    if action == "install":
        return CommandResult("Skill installation is delegated to the skill installer workflow")
    return CommandResult(f"unknown /skills action: {action}", is_error=True)


def _skill_roots(context: CommandContext) -> tuple[Path, ...]:
    return (
        Path.cwd() / ".codex" / "skills",
        context.runtime.settings.home / "skills",
    )


def _discover_skills(roots: tuple[Path, ...]) -> list[tuple[str, Path]]:
    skills: list[tuple[str, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            skill_file = path / "SKILL.md"
            if path.is_dir() and skill_file.exists():
                skills.append((path.name, skill_file))
    return skills


def _render_skills(skills: list[tuple[str, Path]]) -> CommandResult:
    if not skills:
        return CommandResult("No skills discovered", metadata={"count": 0})
    lines = ["Skills"]
    lines.extend(f"  {name:<24} {path}" for name, path in skills)
    return CommandResult("\n".join(lines), metadata={"count": len(skills)})


def _inspect_skill(skills: list[tuple[str, Path]], name: str) -> CommandResult:
    for skill_name, path in skills:
        if skill_name == name:
            return CommandResult(f"{skill_name}: {path}", metadata={"path": str(path)})
    return CommandResult(f"Skill not found: {name}", is_error=True)


SKILL_HANDLERS: dict[str, CommandHandler] = {
    "skills": handle_skills,
}
