import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.runtime.messages import ToolCall, ToolResult
from generic_agent_engineered.tools import (
    DisabledToolError,
    DuplicateToolError,
    FunctionTool,
    ToolPermission,
    ToolRegistry,
    ToolSchema,
    ToolSpec,
    UnknownToolError,
)


def weather_tool() -> FunctionTool:
    return FunctionTool(
        spec=ToolSpec(
            schema=ToolSchema(
                name="weather",
                description="Get weather",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            ),
            permissions=(
                ToolPermission(
                    name="network:http",
                    reason="weather tool calls a remote weather API",
                ),
            ),
        ),
        handler=lambda call: {"content": f"sunny in {call.arguments['city']}"},
    )


class ToolRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_resolve_tool(self):
        registry = ToolRegistry()
        tool = weather_tool()

        registry.register(tool)
        result = await registry.run(
            ToolCall(id="call_1", name="weather", arguments={"city": "Shanghai"})
        )

        self.assertEqual(registry.resolve("weather"), tool)
        self.assertTrue(registry.is_enabled("weather"))
        self.assertEqual(result, ToolResult(tool_use_id="call_1", content="sunny in Shanghai"))
        self.assertEqual(registry.schemas()[0]["name"], "weather")

    def test_duplicate_tool_rejected(self):
        registry = ToolRegistry([weather_tool()])

        with self.assertRaises(DuplicateToolError):
            registry.register(weather_tool())

    async def test_disabled_tool_blocked(self):
        registry = ToolRegistry([weather_tool()])
        registry.disable("weather")

        with self.assertRaises(DisabledToolError):
            registry.resolve("weather")
        self.assertEqual(registry.resolve("weather", include_disabled=True).spec.name, "weather")
        self.assertEqual(registry.schemas(), [])

        result = await registry.run(
            ToolCall(id="call_1", name="weather", arguments={"city": "Shanghai"})
        )

        self.assertTrue(result.is_error)
        self.assertIn("disabled", result.content)

    def test_unknown_tool_rejected_on_strict_lookup(self):
        registry = ToolRegistry()

        with self.assertRaises(UnknownToolError):
            registry.resolve("missing")

    def test_schema_and_permissions_are_separate(self):
        tool = weather_tool()
        schema = tool.spec.schema_dict()

        self.assertEqual(schema["name"], "weather")
        self.assertNotIn("permissions", schema)
        self.assertEqual(tool.spec.permissions[0].name, "network:http")


if __name__ == "__main__":
    unittest.main()
