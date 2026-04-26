import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.auth.store import AuthRecord, AuthStore
from generic_agent_engineered.providers.anthropic_messages import AnthropicMessagesProvider
from generic_agent_engineered.providers.base import ChatMessage
from generic_agent_engineered.providers.codex_oauth import CodexOAuthProvider
from generic_agent_engineered.providers.errors import (
    ProviderAuthError,
    ProviderProtocolError,
    ProviderRateLimitError,
    provider_error_from_status,
)
from generic_agent_engineered.providers.factory import create_provider_client
from generic_agent_engineered.providers.openai_chat import OpenAIChatProvider
from generic_agent_engineered.providers.openai_responses import OpenAIResponsesProvider
from generic_agent_engineered.providers.registry import build_provider_registry
from generic_agent_engineered.providers.tools import (
    parse_tool_arguments,
    to_anthropic_tools,
    to_openai_tools,
)

WEATHER_TOOL = {
    "name": "weather",
    "description": "Get weather",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
    },
}


class FakeResponsesTransport:
    def __init__(self, events):
        self.events = events
        self.payloads = []

    async def stream_responses(self, payload):
        self.payloads.append(payload)
        for event in self.events:
            yield event


class FakeChatTransport:
    def __init__(self, chunks):
        self.chunks = chunks
        self.payloads = []

    async def stream_chat_completions(self, payload):
        self.payloads.append(payload)
        for chunk in self.chunks:
            yield chunk


class FakeAnthropicTransport:
    def __init__(self, events):
        self.events = events
        self.payloads = []

    async def stream_messages(self, payload):
        self.payloads.append(payload)
        for event in self.events:
            yield event


class ProviderClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = build_provider_registry()

    async def test_openai_responses_stream_parsing(self):
        transport = FakeResponsesTransport(
            [
                {"type": "response.output_text.delta", "delta": "hi "},
                {"type": "response.output_text.delta", "delta": "there"},
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "weather",
                        "arguments": '{"city":"Shanghai"}',
                    },
                },
            ]
        )
        provider = OpenAIResponsesProvider(
            self.registry.resolve("openai"),
            "gpt-test",
            transport=transport,
        )

        response = await provider.complete_chat(
            [ChatMessage(role="user", content="hello")],
            tools=[WEATHER_TOOL],
        )

        self.assertEqual(response.content, "hi there")
        self.assertEqual(response.tool_calls[0].id, "call_1")
        self.assertEqual(response.tool_calls[0].arguments, {"city": "Shanghai"})
        payload = transport.payloads[0]
        self.assertEqual(payload["model"], "gpt-test")
        self.assertEqual(payload["tools"][0]["type"], "function")

    async def test_openai_responses_dedupes_duplicate_tool_events(self):
        duplicate_tool_items = [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "call_id": call_id,
                    "id": item_id,
                    "name": "weather",
                    "arguments": '{"city":"Shanghai"}',
                },
            }
            for call_id, item_id in (("call_1", "item_1"), ("call_2", "item_2"))
        ]
        transport = FakeResponsesTransport(
            [
                *duplicate_tool_items,
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {
                                "type": "function_call",
                                "call_id": "call_3",
                                "name": "weather",
                                "arguments": '{"city":"Shanghai"}',
                            }
                        ]
                    },
                },
            ]
        )
        provider = OpenAIResponsesProvider(
            self.registry.resolve("openai"),
            "gpt-test",
            transport=transport,
        )

        events = [
            event
            async for event in provider.stream_chat(
                [ChatMessage(role="user", content="weather")],
                tools=[WEATHER_TOOL],
            )
        ]
        tool_events = [event for event in events if event.kind == "tool_call"]
        response = events[-1].response

        self.assertEqual(len(tool_events), 1)
        self.assertIsNotNone(response)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "weather")
        self.assertEqual(response.tool_calls[0].arguments, {"city": "Shanghai"})

    async def test_openai_chat_stream_parsing(self):
        transport = FakeChatTransport(
            [
                {"choices": [{"delta": {"content": "hello"}}]},
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_2",
                                        "function": {
                                            "name": "weather",
                                            "arguments": '{"city"',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": ':"Beijing"}',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            ]
        )
        provider = OpenAIChatProvider(
            self.registry.resolve("kimi"),
            "moonshot-test",
            transport=transport,
        )

        response = await provider.complete_chat([ChatMessage(role="user", content="hello")])

        self.assertEqual(response.content, "hello")
        self.assertEqual(response.tool_calls[0].id, "call_2")
        self.assertEqual(response.tool_calls[0].arguments, {"city": "Beijing"})
        self.assertEqual(transport.payloads[0]["messages"][0]["content"], "hello")

    async def test_anthropic_messages_stream_parsing(self):
        transport = FakeAnthropicTransport(
            [
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": "done"},
                },
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "weather",
                        "input": {},
                    },
                },
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": '{"city":"Shenzhen"}',
                    },
                },
                {"type": "content_block_stop", "index": 1},
            ]
        )
        provider = AnthropicMessagesProvider(
            self.registry.resolve("anthropic"),
            "claude-test",
            transport=transport,
        )

        response = await provider.complete_chat(
            [
                ChatMessage(role="system", content="be concise"),
                ChatMessage(role="user", content="weather"),
            ],
            tools=[WEATHER_TOOL],
        )

        self.assertEqual(response.content, "done")
        self.assertEqual(response.tool_calls[0].id, "toolu_1")
        self.assertEqual(response.tool_calls[0].arguments, {"city": "Shenzhen"})
        payload = transport.payloads[0]
        self.assertEqual(payload["system"], "be concise")
        self.assertEqual(payload["tools"][0]["input_schema"]["type"], "object")

    async def test_codex_oauth_provider_reads_auth_store_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AuthStore(Path(tmp) / "auth.json")
            store.put(AuthRecord(provider_id="openai-codex", access_token="codex-token"))
            provider = CodexOAuthProvider(
                self.registry.resolve("codex"),
                "codex-test",
                auth_store=store,
            )

            transport = provider._transport_from_auth_store()

        self.assertEqual(transport.api_key, "codex-token")

    async def test_codex_oauth_provider_accepts_mock_transport(self):
        transport = FakeResponsesTransport([{"type": "response.output_text.delta", "delta": "ok"}])
        provider = CodexOAuthProvider(
            self.registry.resolve("codex"),
            "codex-test",
            transport=transport,
        )

        response = await provider.complete_chat([ChatMessage(role="user", content="hello")])

        self.assertEqual(response.content, "ok")
        self.assertEqual(transport.payloads[0]["model"], "codex-test")

    async def test_codex_oauth_provider_requires_login(self):
        provider = CodexOAuthProvider(self.registry.resolve("codex"), "codex-test")

        with self.assertRaises(ProviderAuthError):
            await provider.complete_chat([ChatMessage(role="user", content="hello")])

    def test_tool_schema_conversion_and_json_errors(self):
        openai_tools = to_openai_tools([WEATHER_TOOL])
        anthropic_tools = to_anthropic_tools([openai_tools[0]])

        self.assertEqual(openai_tools[0]["function"]["name"], "weather")
        self.assertEqual(anthropic_tools[0]["name"], "weather")
        self.assertEqual(parse_tool_arguments('{"city":"Hangzhou"}'), {"city": "Hangzhou"})
        with self.assertRaises(ProviderProtocolError):
            parse_tool_arguments("[1, 2]")

    def test_provider_error_mapping(self):
        self.assertIsInstance(provider_error_from_status(429, "slow down"), ProviderRateLimitError)
        self.assertIsInstance(provider_error_from_status(401, "bad token"), ProviderAuthError)

    def test_provider_factory_selects_transport(self):
        provider = create_provider_client(
            self.registry.resolve("dashscope"),
            "qwen-test",
            transport=FakeChatTransport([]),
        )

        self.assertIsInstance(provider, OpenAIChatProvider)


if __name__ == "__main__":
    unittest.main()
