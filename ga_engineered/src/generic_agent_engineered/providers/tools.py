"""Tool schema conversion for provider transports."""

from __future__ import annotations

import json
from typing import Any

from .errors import ProviderProtocolError

EMPTY_PARAMETERS = {"type": "object", "properties": {}}


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderProtocolError("Tool call arguments were not valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ProviderProtocolError("Tool call arguments must decode to a JSON object")


def to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in (_normalize_tool(tool) for tool in tools or [])
    ]


def to_anthropic_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"],
        }
        for tool in (_normalize_tool(tool) for tool in tools or [])
    ]


def _normalize_tool(tool: dict[str, Any]) -> dict[str, Any]:
    if tool.get("type") == "function":
        function = tool.get("function", {})
        name = function.get("name")
        description = function.get("description", "")
        parameters = function.get("parameters") or function.get("input_schema") or EMPTY_PARAMETERS
    else:
        name = tool.get("name")
        description = tool.get("description", "")
        parameters = tool.get("parameters") or tool.get("input_schema") or EMPTY_PARAMETERS

    if not isinstance(name, str) or not name:
        raise ProviderProtocolError("Tool schema is missing a function name")
    if not isinstance(description, str):
        raise ProviderProtocolError("Tool schema description must be a string")
    if not isinstance(parameters, dict):
        raise ProviderProtocolError("Tool schema parameters must be an object")

    return {
        "name": name,
        "description": description,
        "parameters": parameters,
    }
