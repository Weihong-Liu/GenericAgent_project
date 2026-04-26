"""Browser session and bridge adapters.

The first implementation keeps the old TMWebDriver contract available while
moving session state into this package. A future native CDP transport can
implement the same BrowserBridge protocol without changing browser tools.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

ExecutionStatus = Literal["success", "failed"]


class BrowserSessionError(RuntimeError):
    """Raised when browser session state is missing or invalid."""


@dataclass(frozen=True)
class BrowserSession:
    id: str
    url: str = ""
    title: str = ""
    type: str = "unknown"
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("browser session id is required")
        if not isinstance(self.metadata, dict):
            raise TypeError("browser session metadata must be a dict")

    @classmethod
    def from_raw(
        cls,
        raw_session: BrowserSession | Mapping[str, Any] | tuple[Any, Any],
    ) -> BrowserSession:
        if isinstance(raw_session, BrowserSession):
            return raw_session
        if isinstance(raw_session, tuple) and len(raw_session) == 2:
            session_id, info = raw_session
            if not isinstance(info, Mapping):
                raise TypeError("browser session tuple info must be a mapping")
            data = {"id": str(session_id), **dict(info)}
        elif isinstance(raw_session, Mapping):
            data = dict(raw_session)
        else:
            raise TypeError("browser session must be a mapping or BrowserSession")

        session_id = _session_id(data)
        active = bool(data.get("active", data.get("is_active", True)))
        known_keys = {
            "id",
            "sessionId",
            "session_id",
            "tabId",
            "tab_id",
            "targetId",
            "url",
            "title",
            "type",
            "active",
            "is_active",
        }
        metadata = {key: value for key, value in data.items() if key not in known_keys}
        return cls(
            id=session_id,
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
            type=str(data.get("type", "unknown")),
            active=active,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "type": self.type,
            "active": self.active,
        }
        payload.update(self.metadata)
        return payload


@dataclass(frozen=True)
class BrowserExecution:
    status: ExecutionStatus
    js_return: Any = None
    error: str = ""
    new_tabs: tuple[dict[str, Any], ...] = ()
    reloaded: bool = False
    raw: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "new_tabs", tuple(self.new_tabs))
        if self.status not in {"success", "failed"}:
            raise ValueError("browser execution status must be success or failed")

    @property
    def successful(self) -> bool:
        return self.status == "success"

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "js_return": self.js_return,
        }
        if self.error:
            payload["error"] = self.error
        if self.new_tabs:
            payload["newTabs"] = list(self.new_tabs)
        if self.reloaded:
            payload["reloaded"] = True
        return payload


@runtime_checkable
class BrowserBridge(Protocol):
    def list_sessions(self) -> Sequence[BrowserSession | Mapping[str, Any]]:
        """Return active browser sessions."""

    def execute_js(
        self,
        script: str,
        *,
        session_id: str | None = None,
        timeout: float = 15.0,
    ) -> Any:
        """Execute JavaScript and return a bridge-specific result shape."""


@dataclass
class BrowserSessionStore:
    sessions: dict[str, BrowserSession] = field(default_factory=dict)
    active_session_id: str | None = None

    def refresh(
        self,
        raw_sessions: Sequence[BrowserSession | Mapping[str, Any] | tuple[Any, Any]],
    ) -> tuple[BrowserSession, ...]:
        normalized = tuple(BrowserSession.from_raw(raw) for raw in raw_sessions)
        normalized = tuple(session for session in normalized if session.active)
        self.sessions = {session.id: session for session in normalized}
        if self.active_session_id not in self.sessions:
            current = next(
                (session for session in normalized if session.metadata.get("current") is True),
                None,
            )
            self.active_session_id = (current or normalized[0]).id if normalized else None
        return normalized

    def select(
        self,
        session_id: str | None = None,
        *,
        url_pattern: str | None = None,
    ) -> BrowserSession:
        if session_id:
            if session_id not in self.sessions:
                raise BrowserSessionError(f"browser session not found: {session_id}")
            self.active_session_id = session_id
            return self.sessions[session_id]

        if url_pattern:
            matches = [session for session in self.sessions.values() if url_pattern in session.url]
            if not matches:
                raise BrowserSessionError(f"browser session url not found: {url_pattern}")
            self.active_session_id = matches[0].id
            return matches[0]

        return self.active()

    def active(self) -> BrowserSession:
        if self.active_session_id and self.active_session_id in self.sessions:
            return self.sessions[self.active_session_id]
        raise BrowserSessionError("no active browser session")

    def to_tabs(self) -> list[dict[str, Any]]:
        return [
            {
                "id": session.id,
                "url": session.url,
                "title": session.title,
                "type": session.type,
            }
            for session in self.sessions.values()
        ]


@dataclass
class TmWebDriverBridge:
    """Adapter for the legacy TMWebDriver object."""

    driver: Any

    def list_sessions(self) -> tuple[BrowserSession, ...]:
        return tuple(BrowserSession.from_raw(session) for session in self.driver.get_all_sessions())

    def execute_js(
        self,
        script: str,
        *,
        session_id: str | None = None,
        timeout: float = 15.0,
    ) -> Any:
        return self.driver.execute_js(script, timeout=timeout, session_id=session_id)


@dataclass(frozen=True)
class CdpBridge:
    """HTTP bridge compatible with TMWebDriver's remote /link endpoint."""

    endpoint: str = "http://127.0.0.1:18766/link"
    request_timeout: float = 15.0
    request_timeout_margin: float = 5.0

    def list_sessions(self) -> tuple[BrowserSession, ...]:
        raw = self._post({"cmd": "get_all_sessions"})
        if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
            raise BrowserSessionError("browser bridge returned invalid session list")
        return tuple(BrowserSession.from_raw(session) for session in raw)

    def execute_js(
        self,
        script: str,
        *,
        session_id: str | None = None,
        timeout: float = 15.0,
    ) -> Any:
        return self._post(
            {
                "cmd": "execute_js",
                "sessionId": session_id,
                "code": script,
                "timeout": str(timeout),
            },
            request_timeout=max(self.request_timeout, timeout + self.request_timeout_margin),
        )

    def _post(self, payload: dict[str, Any], *, request_timeout: float | None = None) -> Any:
        import httpx

        try:
            with httpx.Client(
                timeout=request_timeout if request_timeout is not None else self.request_timeout,
                trust_env=False,
            ) as client:
                response = client.post(
                    self.endpoint,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            message = (
                f"browser bridge unavailable at {self.endpoint}: {exc}. "
                "Start or restart it with `uv run gae bridge`, then make sure "
                "the bundled Chrome extension is loaded and connected."
            )
            raise BrowserSessionError(message) from exc
        data = response.json()
        if isinstance(data, Mapping) and "r" in data:
            return data["r"]
        return data


def normalize_execute_result(raw_result: Any) -> BrowserExecution:
    if isinstance(raw_result, BrowserExecution):
        return raw_result

    if isinstance(raw_result, Mapping):
        raw = dict(raw_result)
        error = raw.get("error")
        if error:
            return BrowserExecution(
                status="failed",
                js_return=None,
                error=_stringify(error),
                new_tabs=_normalize_new_tabs(raw),
                reloaded=_is_reloaded(raw),
                raw=raw_result,
            )

        if "data" in raw:
            js_return = raw["data"]
        elif "js_return" in raw:
            js_return = raw["js_return"]
        elif "result" in raw:
            js_return = raw["result"]
        else:
            js_return = raw

        return BrowserExecution(
            status="success",
            js_return=js_return,
            new_tabs=_normalize_new_tabs(raw),
            reloaded=_is_reloaded(raw),
            raw=raw_result,
        )

    return BrowserExecution(status="success", js_return=raw_result, raw=raw_result)


def _session_id(data: Mapping[str, Any]) -> str:
    for key in ("id", "sessionId", "session_id", "tabId", "tab_id", "targetId"):
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    raise ValueError("browser session id is required")


def _normalize_new_tabs(raw: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    tabs = raw.get("newTabs", raw.get("new_tabs", ()))
    if not isinstance(tabs, Sequence) or isinstance(tabs, str | bytes):
        return ()
    normalized: list[dict[str, Any]] = []
    for tab in tabs:
        if isinstance(tab, BrowserSession):
            normalized.append(tab.to_dict())
        elif isinstance(tab, Mapping):
            normalized.append(BrowserSession.from_raw(tab).to_dict())
    return tuple(normalized)


def _is_reloaded(raw: Mapping[str, Any]) -> bool:
    return bool(raw.get("reloaded") or raw.get("closed") == 1)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
