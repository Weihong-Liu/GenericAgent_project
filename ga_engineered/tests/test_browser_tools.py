import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.browser import (
    BrowserSession,
    BrowserSessionStore,
    CdpBridge,
    normalize_execute_result,
    simplify_html,
)
from generic_agent_engineered.runtime.messages import ToolCall
from generic_agent_engineered.tools import WebExecuteJsTool, WebOpenTool, WebScanTool


class FakeBridge:
    def __init__(self, sessions: list[dict[str, Any]], result: Any = None) -> None:
        self.sessions = sessions
        self.result = result if result is not None else {"data": "<html><body>ok</body></html>"}
        self.calls: list[dict[str, Any]] = []

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.sessions

    def execute_js(
        self,
        script: str,
        *,
        session_id: str | None = None,
        timeout: float = 15.0,
    ) -> Any:
        self.calls.append({"script": script, "session_id": session_id, "timeout": timeout})
        return self.result() if callable(self.result) else self.result


def _payload(result_content: str) -> dict[str, Any]:
    return json.loads(result_content)


class BrowserToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_open_opens_search_query(self):
        opened: list[str] = []
        tool = WebOpenTool(open_browser=lambda url: opened.append(url) is None or True)

        result = await tool.run(
            ToolCall(
                id="call_1",
                name="web_open",
                arguments={"query": "今天徐州天气"},
            )
        )
        payload = _payload(result.content)

        self.assertFalse(result.is_error)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(opened, [payload["url"]])
        self.assertIn("%E4%BB%8A%E5%A4%A9", payload["url"])

    async def test_web_open_rejects_non_http_url(self):
        tool = WebOpenTool(open_browser=lambda _url: True)

        result = await tool.run(
            ToolCall(id="call_1", name="web_open", arguments={"url": "file:///tmp/a"})
        )

        self.assertTrue(result.is_error)
        self.assertIn("http(s)", result.content)

    async def test_session_list_parsing_and_selection_state(self):
        bridge = FakeBridge(
            [
                {"id": "tab-1", "url": "https://example.com", "title": "One", "type": "ext_ws"},
                {"tabId": 2, "url": "https://docs.example.com", "title": "Two"},
            ]
        )
        store = BrowserSessionStore()
        scan_tool = WebScanTool(bridge, session_store=store)

        first = await scan_tool.run(
            ToolCall(id="call_1", name="web_scan", arguments={"tabs_only": True})
        )
        second = await scan_tool.run(
            ToolCall(
                id="call_2",
                name="web_scan",
                arguments={"tabs_only": True, "switch_tab_id": "2"},
            )
        )

        self.assertFalse(first.is_error)
        self.assertFalse(second.is_error)
        self.assertEqual(_payload(first.content)["metadata"]["tabs_count"], 2)
        self.assertEqual(_payload(second.content)["metadata"]["active_tab"], "2")
        self.assertEqual(store.active().url, "https://docs.example.com")
        self.assertEqual(bridge.calls, [])

    async def test_session_refresh_prefers_current_browser_tab_initially(self):
        bridge = FakeBridge(
            [
                {"id": "tab-1", "url": "https://old.example.com", "title": "Old"},
                {"id": "tab-2", "url": "https://x.com/explore", "title": "X", "current": True},
            ]
        )
        store = BrowserSessionStore()
        scan_tool = WebScanTool(bridge, session_store=store)

        result = await scan_tool.run(
            ToolCall(id="call_1", name="web_scan", arguments={"tabs_only": True})
        )

        self.assertFalse(result.is_error)
        self.assertEqual(_payload(result.content)["metadata"]["active_tab"], "tab-2")

    def test_html_simplification_removes_noise(self):
        raw_html = """
        <html><head><meta charset="utf-8"><style>.x{}</style><script>alert(1)</script></head>
        <body>
          <div hidden>secret</div>
          <div aria-hidden="true">ignored</div>
          <nav style="position: fixed">floating nav</nav>
          <main><button onclick="bad()" data-testid="go">Go</button></main>
        </body></html>
        """

        simplified = simplify_html(raw_html, max_chars=500)

        self.assertIn("Go", simplified.content)
        self.assertIn('data-testid="go"', simplified.content)
        self.assertNotIn("alert", simplified.content)
        self.assertNotIn("secret", simplified.content)
        self.assertNotIn("floating nav", simplified.content)
        self.assertNotIn("onclick", simplified.content)
        self.assertFalse(simplified.truncated)

    async def test_web_scan_simplifies_and_applies_budget(self):
        long_html = "<html><body><main>" + ("visible " * 80) + "</main></body></html>"
        bridge = FakeBridge([{"id": "tab-1", "url": "https://example.com"}], {"data": long_html})
        tool = WebScanTool(
            bridge,
            default_output_chars=90,
            max_output_chars=90,
        )

        result = await tool.run(ToolCall(id="call_1", name="web_scan", arguments={}))
        payload = _payload(result.content)

        self.assertFalse(result.is_error)
        self.assertTrue(result.metadata["truncated"])
        self.assertIn("[TRUNCATED]", payload["content"])
        self.assertEqual(bridge.calls[0]["session_id"], "tab-1")

    async def test_execute_js_result_normalization(self):
        bridge = FakeBridge(
            [{"id": "tab-1", "url": "https://example.com"}],
            {"data": {"answer": 42}, "newTabs": [{"id": "tab-2", "url": "https://new.example"}]},
        )
        tool = WebExecuteJsTool(bridge)

        result = await tool.run(
            ToolCall(
                id="call_1",
                name="web_execute_js",
                arguments={"script": "return 42", "timeout": 3},
            )
        )
        payload = _payload(result.content)

        self.assertFalse(result.is_error)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["js_return"], {"answer": 42})
        self.assertEqual(payload["newTabs"][0]["id"], "tab-2")
        self.assertEqual(result.metadata["new_tabs"], 1)
        self.assertEqual(bridge.calls[0]["timeout"], 3.0)

    async def test_execute_js_budget_and_safe_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = FakeBridge(
                [{"id": "tab-1", "url": "https://example.com"}],
                {"data": "x" * 200},
            )
            tool = WebExecuteJsTool(
                bridge,
                workspace_root=root,
                default_output_chars=80,
                max_output_chars=80,
            )

            result = await tool.run(
                ToolCall(
                    id="call_1",
                    name="web_execute_js",
                    arguments={
                        "script": "return document.body.innerText",
                        "save_to_file": "out.txt",
                    },
                )
            )
            payload = _payload(result.content)

            self.assertFalse(result.is_error)
            self.assertTrue(result.metadata["truncated"])
            self.assertIn("[TRUNCATED]", payload["js_return"])
            self.assertEqual(payload["saved_to_file"], "out.txt")
            self.assertEqual((root / "out.txt").read_text(encoding="utf-8"), "x" * 200)

    def test_execute_js_error_shape_normalized(self):
        result = normalize_execute_result({"error": {"message": "boom"}, "closed": 1})

        self.assertFalse(result.successful)
        self.assertEqual(result.error, '{"message": "boom"}')
        self.assertTrue(result.reloaded)

    def test_browser_session_tuple_compatibility(self):
        session = BrowserSession.from_raw(("tab-1", {"url": "https://example.com"}))

        self.assertEqual(session.id, "tab-1")
        self.assertEqual(session.url, "https://example.com")

    def test_cdp_bridge_bypasses_proxy_environment(self):
        captured: dict[str, Any] = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return {"r": [{"id": "tab-1", "url": "https://example.com"}]}

        class FakeClient:
            def __init__(self, *, timeout: float, trust_env: bool) -> None:
                captured["timeout"] = timeout
                captured["trust_env"] = trust_env

            def __enter__(self) -> "FakeClient":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def post(
                self,
                endpoint: str,
                *,
                headers: dict[str, str],
                json: dict[str, Any],
            ) -> FakeResponse:
                captured["endpoint"] = endpoint
                captured["headers"] = headers
                captured["payload"] = json
                return FakeResponse()

        with patch("httpx.Client", FakeClient):
            sessions = CdpBridge(request_timeout=3.0).list_sessions()

        self.assertFalse(captured["trust_env"])
        self.assertEqual(captured["timeout"], 3.0)
        self.assertEqual(captured["payload"], {"cmd": "get_all_sessions"})
        self.assertEqual(sessions[0].id, "tab-1")

    def test_cdp_execute_js_request_timeout_has_margin_over_script_timeout(self):
        captured: dict[str, Any] = {}

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return {"r": {"data": "ok"}}

        class FakeClient:
            def __init__(self, *, timeout: float, trust_env: bool) -> None:
                captured["timeout"] = timeout
                captured["trust_env"] = trust_env

            def __enter__(self) -> "FakeClient":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def post(
                self,
                endpoint: str,
                *,
                headers: dict[str, str],
                json: dict[str, Any],
            ) -> FakeResponse:
                captured["payload"] = json
                return FakeResponse()

        with patch("httpx.Client", FakeClient):
            result = CdpBridge(request_timeout=3.0, request_timeout_margin=4.0).execute_js(
                "return 1",
                session_id="tab-1",
                timeout=10.0,
            )

        self.assertEqual(result, {"data": "ok"})
        self.assertEqual(captured["timeout"], 14.0)
        self.assertEqual(captured["payload"]["timeout"], "10.0")


if __name__ == "__main__":
    unittest.main()
