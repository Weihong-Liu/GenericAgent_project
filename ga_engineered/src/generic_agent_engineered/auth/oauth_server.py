"""Loopback OAuth callback server."""

from __future__ import annotations

import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class OAuthCallbackResult:
    code: str
    state: str
    error: str
    error_description: str
    raw_query: dict[str, str]


def parse_callback_path(path: str) -> OAuthCallbackResult:
    parsed = urllib.parse.urlparse(path)
    query = urllib.parse.parse_qs(parsed.query)
    raw_query = {key: values[0] for key, values in query.items() if values}
    return OAuthCallbackResult(
        code=raw_query.get("code", ""),
        state=raw_query.get("state", ""),
        error=raw_query.get("error", ""),
        error_description=raw_query.get("error_description", ""),
        raw_query=raw_query,
    )


class LoopbackOAuthServer:
    """Small one-shot HTTP server for OAuth loopback callbacks."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        callback_path: str = "/callback",
    ) -> None:
        self.host = host
        self.callback_path = callback_path
        self._server = ThreadingHTTPServer((host, port), self._build_handler())
        self._result: OAuthCallbackResult | None = None
        self._event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def redirect_uri(self) -> str:
        return f"http://{self.host}:{self.port}{self.callback_path}"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="oauth-loopback-server",
            daemon=True,
        )
        self._thread.start()

    def wait(self, timeout_seconds: float = 120.0) -> OAuthCallbackResult:
        if not self._event.wait(timeout_seconds):
            raise TimeoutError("Timed out waiting for OAuth callback")
        if self._result is None:
            raise TimeoutError("OAuth callback completed without a result")
        return self._result

    def close(self) -> None:
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(timeout=2)
        self._server.server_close()

    def __enter__(self) -> LoopbackOAuthServer:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != outer.callback_path:
                    self.send_error(404)
                    return

                result = parse_callback_path(self.path)
                outer._result = result
                outer._event.set()
                if result.error:
                    self._send_text(400, "OAuth login failed. You may close this window.")
                    return
                self._send_text(200, "OAuth login complete. You may close this window.")

            def log_message(self, format: str, *args: object) -> None:
                return

            def _send_text(self, status: int, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return CallbackHandler
