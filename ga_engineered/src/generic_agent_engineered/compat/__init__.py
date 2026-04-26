"""Legacy GenericAgent compatibility helpers."""

from .legacy import (
    LEGACY_ENTRYPOINT_MIGRATIONS,
    LEGACY_TOOL_MIGRATIONS,
    LegacyEntrypointMigration,
    LegacyReflectResult,
    LegacyTaskResult,
    LegacyToolMigration,
    legacy_tool_names,
    run_reflect_once,
    run_task_io,
)

__all__ = [
    "LEGACY_ENTRYPOINT_MIGRATIONS",
    "LEGACY_TOOL_MIGRATIONS",
    "LegacyEntrypointMigration",
    "LegacyReflectResult",
    "LegacyTaskResult",
    "LegacyToolMigration",
    "legacy_tool_names",
    "run_reflect_once",
    "run_task_io",
]
