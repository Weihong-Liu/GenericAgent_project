"""JSON-RPC frame types and codecs for the TypeScript TUI gateway.

The wire protocol is line-delimited JSON over stdio. See
``tasks/TUI_TS_PROTOCOL.md`` for the authoritative spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = "1.0"

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_RUNTIME_BUSY = -32001
ERR_REQUEST_REJECTED = -32002
ERR_AUTH_REQUIRED = -32003
ERR_PROVIDER_FAILURE = -32004
ERR_UNKNOWN = -32099


class ProtocolError(Exception):
    """Raised when an inbound frame is malformed or a method rejects its input."""

    def __init__(
        self,
        code: int,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        request_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = dict(data or {})
        self.request_id = request_id

    def to_error_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data:
            out["data"] = self.data
        return out


@dataclass(frozen=True)
class Request:
    id: int
    method: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    id: int
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_frame(self) -> dict[str, Any]:
        if self.error is not None:
            return {"type": "response", "id": self.id, "error": self.error}
        return {"type": "response", "id": self.id, "result": self.result or {}}


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: int | None = None

    def to_frame(self) -> dict[str, Any]:
        frame: dict[str, Any] = {
            "type": "event",
            "kind": self.kind,
            "payload": self.payload,
        }
        if self.request_id is not None:
            frame["request_id"] = self.request_id
        return frame


def encode_frame(frame: dict[str, Any]) -> str:
    """Serialize a single frame as a UTF-8 JSON line.

    Always returns a trailing newline. Uses ``default=str`` so unexpected
    objects (e.g. ``Path``) become strings rather than crashing the gateway.
    """

    return json.dumps(frame, ensure_ascii=False, default=str) + "\n"


def parse_request(line: str) -> Request:
    """Parse one request frame.

    Raises ``ProtocolError`` with the appropriate JSON-RPC error code on
    malformed input. The caller is responsible for surfacing the error as a
    response frame; this function does not write to the wire.
    """

    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(ERR_PARSE, f"invalid JSON frame: {exc}") from exc

    if not isinstance(obj, dict):
        raise ProtocolError(ERR_INVALID_REQUEST, "frame must be a JSON object")

    rid = obj.get("id")
    if not isinstance(rid, int) or isinstance(rid, bool):
        raise ProtocolError(ERR_INVALID_REQUEST, "request id must be an integer")

    if obj.get("type") != "request":
        raise ProtocolError(
            ERR_INVALID_REQUEST,
            "expected type=request",
            request_id=rid,
        )

    method = obj.get("method")
    if not isinstance(method, str) or not method:
        raise ProtocolError(
            ERR_INVALID_REQUEST,
            "method is required",
            request_id=rid,
        )

    params = obj.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ProtocolError(
            ERR_INVALID_PARAMS,
            "params must be an object",
            request_id=rid,
        )

    return Request(id=rid, method=method, params=params)


__all__ = [
    "ERR_AUTH_REQUIRED",
    "ERR_INVALID_PARAMS",
    "ERR_INVALID_REQUEST",
    "ERR_METHOD_NOT_FOUND",
    "ERR_PARSE",
    "ERR_PROVIDER_FAILURE",
    "ERR_REQUEST_REJECTED",
    "ERR_RUNTIME_BUSY",
    "ERR_UNKNOWN",
    "Event",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "Request",
    "Response",
    "encode_frame",
    "parse_request",
]
