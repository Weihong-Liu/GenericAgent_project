"""Stdio JSON-RPC gateway between the TS TUI frontend and the Python runtime."""

from .protocol import (
    PROTOCOL_VERSION,
    Event,
    ProtocolError,
    Request,
    Response,
    encode_frame,
    parse_request,
)
from .server import GatewayServer, serve_stdio

__all__ = [
    "Event",
    "GatewayServer",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "Request",
    "Response",
    "encode_frame",
    "parse_request",
    "serve_stdio",
]
