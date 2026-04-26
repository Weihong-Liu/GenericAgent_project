"""Small HTTP/SSE transport helpers for provider clients."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .errors import ProviderProtocolError, provider_error_from_status


@dataclass(frozen=True)
class SSEJSONTransport:
    base_url: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 120.0

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required for live provider HTTP transport") from exc

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        ) as client, client.stream(
            "POST",
            self.path,
            json=payload,
            headers=self.headers,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                message = body.decode("utf-8", errors="replace")
                raise provider_error_from_status(response.status_code, message)

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    decoded = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ProviderProtocolError("Provider stream emitted invalid JSON") from exc
                if isinstance(decoded, dict):
                    yield decoded
                else:
                    raise ProviderProtocolError("Provider stream event must be a JSON object")
