"""Unit tests for the gateway frame codec and validators."""

from __future__ import annotations

import json

import pytest

from generic_agent_engineered.gateway.protocol import (
    ERR_INVALID_PARAMS,
    ERR_INVALID_REQUEST,
    ERR_PARSE,
    PROTOCOL_VERSION,
    Event,
    ProtocolError,
    Request,
    Response,
    encode_frame,
    parse_request,
)


def test_protocol_version_is_one() -> None:
    assert PROTOCOL_VERSION == "1.0"


class TestEncodeFrame:
    def test_appends_newline(self) -> None:
        line = encode_frame({"type": "event", "kind": "ping", "payload": {}})
        assert line.endswith("\n")
        # Exactly one newline.
        assert line.count("\n") == 1

    def test_round_trips_unicode(self) -> None:
        line = encode_frame({"type": "event", "kind": "x", "payload": {"v": "你好"}})
        parsed = json.loads(line)
        assert parsed["payload"]["v"] == "你好"

    def test_handles_unserializable_via_default_str(self) -> None:
        from pathlib import Path

        line = encode_frame({"type": "event", "kind": "x", "payload": {"p": Path("/tmp")}})
        parsed = json.loads(line)
        assert parsed["payload"]["p"] == "/tmp"


class TestParseRequest:
    def test_parses_valid_request(self) -> None:
        line = '{"type":"request","id":7,"method":"runtime.status","params":{}}'
        request = parse_request(line)
        assert request == Request(id=7, method="runtime.status", params={})

    def test_missing_params_defaults_to_empty(self) -> None:
        line = '{"type":"request","id":1,"method":"session.new"}'
        request = parse_request(line)
        assert request.params == {}

    def test_null_params_defaults_to_empty(self) -> None:
        line = '{"type":"request","id":1,"method":"session.new","params":null}'
        request = parse_request(line)
        assert request.params == {}

    def test_invalid_json_returns_parse_error(self) -> None:
        with pytest.raises(ProtocolError) as exc_info:
            parse_request("{not json")
        assert exc_info.value.code == ERR_PARSE

    def test_non_object_frame_rejected(self) -> None:
        with pytest.raises(ProtocolError) as exc_info:
            parse_request("[]")
        assert exc_info.value.code == ERR_INVALID_REQUEST

    def test_wrong_type_field_rejected(self) -> None:
        line = '{"type":"event","id":1,"method":"x"}'
        with pytest.raises(ProtocolError) as exc_info:
            parse_request(line)
        assert exc_info.value.code == ERR_INVALID_REQUEST
        assert exc_info.value.request_id == 1

    def test_missing_method_rejected(self) -> None:
        line = '{"type":"request","id":1}'
        with pytest.raises(ProtocolError) as exc_info:
            parse_request(line)
        assert exc_info.value.code == ERR_INVALID_REQUEST

    def test_non_integer_id_rejected(self) -> None:
        line = '{"type":"request","id":"abc","method":"x"}'
        with pytest.raises(ProtocolError) as exc_info:
            parse_request(line)
        assert exc_info.value.code == ERR_INVALID_REQUEST

    def test_boolean_id_rejected(self) -> None:
        # Python's int(True) == 1, but JSON-RPC ids must be ints, not booleans.
        line = '{"type":"request","id":true,"method":"x"}'
        with pytest.raises(ProtocolError) as exc_info:
            parse_request(line)
        assert exc_info.value.code == ERR_INVALID_REQUEST

    def test_non_object_params_rejected(self) -> None:
        line = '{"type":"request","id":1,"method":"x","params":[]}'
        with pytest.raises(ProtocolError) as exc_info:
            parse_request(line)
        assert exc_info.value.code == ERR_INVALID_PARAMS
        assert exc_info.value.request_id == 1


class TestResponseAndEventFrames:
    def test_response_success_frame(self) -> None:
        frame = Response(id=3, result={"ok": True}).to_frame()
        assert frame == {"type": "response", "id": 3, "result": {"ok": True}}

    def test_response_error_frame(self) -> None:
        frame = Response(id=3, error={"code": -32001, "message": "busy"}).to_frame()
        assert frame == {
            "type": "response",
            "id": 3,
            "error": {"code": -32001, "message": "busy"},
        }

    def test_event_with_request_id(self) -> None:
        frame = Event(
            kind="content_delta", payload={"delta": "hi"}, request_id=2
        ).to_frame()
        assert frame == {
            "type": "event",
            "kind": "content_delta",
            "payload": {"delta": "hi"},
            "request_id": 2,
        }

    def test_event_without_request_id(self) -> None:
        frame = Event(kind="gateway.ready", payload={"v": "1"}).to_frame()
        assert frame == {
            "type": "event",
            "kind": "gateway.ready",
            "payload": {"v": "1"},
        }
