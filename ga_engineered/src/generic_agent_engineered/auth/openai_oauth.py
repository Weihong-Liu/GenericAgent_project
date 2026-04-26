"""OpenAI Codex OAuth PKCE flow primitives."""

from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .store import AuthRecord, AuthStore, create_pkce_challenge, create_pkce_pair

PROVIDER_ID = "openai-codex"
DEFAULT_AUTHORIZATION_ENDPOINT = "https://openai.com/oauth/authorize"
DEFAULT_TOKEN_ENDPOINT = "https://openai.com/oauth/token"
DEFAULT_CLIENT_ID = "claude-code-client"
DEFAULT_SCOPES = ("api", "codex")


class OAuthError(RuntimeError):
    """Base error for OAuth flow failures."""


class OAuthStateMismatch(OAuthError):
    """Raised when the callback state does not match the login session."""


class OAuthCallbackError(OAuthError):
    """Raised when the callback does not contain an authorization code."""


class OAuthTokenError(OAuthError):
    """Raised when token exchange or refresh fails."""


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str = DEFAULT_CLIENT_ID
    authorization_endpoint: str = DEFAULT_AUTHORIZATION_ENDPOINT
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    redirect_host: str = "127.0.0.1"
    redirect_path: str = "/callback"


@dataclass(frozen=True)
class OAuthSession:
    provider_id: str
    state: str
    verifier: str
    challenge: str
    redirect_uri: str
    authorization_url: str


class OAuthTokenTransport(Protocol):
    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        """POST x-www-form-urlencoded data and return a decoded JSON body."""
        ...


@dataclass(frozen=True)
class UrllibOAuthTokenTransport:
    timeout_seconds: float = 30.0

    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            message = f"Token request failed with HTTP {exc.code}: {error_body}"
            raise OAuthTokenError(message) from exc
        except urllib.error.URLError as exc:
            raise OAuthTokenError(f"Token request failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise OAuthTokenError("Token response was not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise OAuthTokenError("Token response must be a JSON object")
        return decoded


@dataclass(frozen=True)
class OpenAICodexOAuthClient:
    config: OAuthConfig = OAuthConfig()
    transport: OAuthTokenTransport = UrllibOAuthTokenTransport()

    def create_login_session(
        self,
        port: int,
        *,
        state: str | None = None,
        verifier: str | None = None,
    ) -> OAuthSession:
        if port <= 0:
            raise ValueError("port must be a positive loopback port")

        effective_state = state or secrets.token_urlsafe(32)
        if verifier is None:
            effective_verifier, challenge = create_pkce_pair()
        else:
            effective_verifier = verifier
            challenge = create_pkce_challenge(verifier)

        redirect_uri = self._redirect_uri(port)
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.config.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": effective_state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        authorization_url = f"{self.config.authorization_endpoint}?{query}"
        return OAuthSession(
            provider_id=PROVIDER_ID,
            state=effective_state,
            verifier=effective_verifier,
            challenge=challenge,
            redirect_uri=redirect_uri,
            authorization_url=authorization_url,
        )

    def extract_authorization_code(self, callback_url: str, session: OAuthSession) -> str:
        parsed = urllib.parse.urlparse(callback_url)
        query = urllib.parse.parse_qs(parsed.query)
        callback_state = _single(query, "state")
        if callback_state != session.state:
            raise OAuthStateMismatch("OAuth callback state did not match the login session")

        error = _single(query, "error")
        if error:
            description = _single(query, "error_description")
            suffix = f": {description}" if description else ""
            raise OAuthCallbackError(f"OAuth callback returned {error}{suffix}")

        code = _single(query, "code")
        if not code:
            raise OAuthCallbackError("OAuth callback did not include an authorization code")
        return code

    def exchange_code(
        self,
        session: OAuthSession,
        code: str,
        *,
        now: float | None = None,
    ) -> AuthRecord:
        payload = self.transport.post_form(
            self.config.token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": session.redirect_uri,
                "code_verifier": session.verifier,
                "client_id": self.config.client_id,
            },
        )
        return self._record_from_token_response(payload, now=_now(now))

    def refresh(self, record: AuthRecord, *, now: float | None = None) -> AuthRecord:
        if not record.refresh_token:
            raise OAuthTokenError("Cannot refresh OAuth token without a refresh token")

        payload = self.transport.post_form(
            self.config.token_endpoint,
            {
                "grant_type": "refresh_token",
                "refresh_token": record.refresh_token,
                "client_id": self.config.client_id,
            },
        )
        return self._record_from_token_response(
            payload,
            now=_now(now),
            previous_refresh_token=record.refresh_token,
        )

    def refresh_if_needed(
        self,
        store: AuthStore,
        *,
        skew_seconds: int = 120,
        now: float | None = None,
    ) -> AuthRecord | None:
        record = store.get(PROVIDER_ID)
        if record is None:
            return None
        effective_now = _now(now)
        if not _is_expired(record, skew_seconds=skew_seconds, now=effective_now):
            return record
        refreshed = self.refresh(record, now=effective_now)
        store.put(refreshed)
        return refreshed

    def logout(self, store: AuthStore) -> None:
        store.delete(PROVIDER_ID)

    def _redirect_uri(self, port: int) -> str:
        return f"http://{self.config.redirect_host}:{port}{self.config.redirect_path}"

    def _record_from_token_response(
        self,
        payload: dict[str, Any],
        *,
        now: float,
        previous_refresh_token: str = "",
    ) -> AuthRecord:
        access_token = _string(payload, "access_token")
        if not access_token:
            raise OAuthTokenError("Token response did not include access_token")

        expires_at = None
        expires_in = payload.get("expires_in")
        if expires_in is not None:
            try:
                expires_at = now + float(expires_in)
            except (TypeError, ValueError) as exc:
                raise OAuthTokenError("Token response expires_in must be numeric") from exc

        refresh_token = _string(payload, "refresh_token") or previous_refresh_token
        metadata = {
            key: payload[key]
            for key in ("token_type", "scope")
            if key in payload and payload[key] is not None
        }
        return AuthRecord(
            provider_id=PROVIDER_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            metadata=metadata or None,
        )


def _single(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    if not values:
        return ""
    return values[0]


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _now(value: float | None) -> float:
    return time.time() if value is None else value


def _is_expired(record: AuthRecord, *, skew_seconds: int, now: float) -> bool:
    if record.expires_at is None:
        return False
    return now >= record.expires_at - skew_seconds
