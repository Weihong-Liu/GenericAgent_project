"""Assemble command handlers without coupling handlers to registry metadata."""

from __future__ import annotations

from .base import CommandHandler
from .config import CONFIG_HANDLERS
from .extensions import EXTENSION_HANDLERS
from .integrations import INTEGRATION_HANDLERS
from .local import LOCAL_HANDLERS
from .memory import MEMORY_HANDLERS
from .permissions import PERMISSION_HANDLERS
from .session import SESSION_HANDLERS
from .skills import SKILL_HANDLERS
from .tools import TOOL_HANDLERS


def build_command_handlers() -> dict[str, CommandHandler]:
    handlers: dict[str, CommandHandler] = {}
    for group in (
        SESSION_HANDLERS,
        CONFIG_HANDLERS,
        LOCAL_HANDLERS,
        TOOL_HANDLERS,
        PERMISSION_HANDLERS,
        MEMORY_HANDLERS,
        SKILL_HANDLERS,
        EXTENSION_HANDLERS,
        INTEGRATION_HANDLERS,
    ):
        handlers.update(group)
    return handlers
