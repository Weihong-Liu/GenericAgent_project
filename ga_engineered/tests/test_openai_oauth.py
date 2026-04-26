import errno
import sys
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generic_agent_engineered.auth.oauth_server import LoopbackOAuthServer
from generic_agent_engineered.auth.openai_oauth import (
    DEFAULT_CLIENT_ID,
    OAuthStateMismatch,
    OpenAICodexOAuthClient,
)
from generic_agent_engineered.auth.store import AuthRecord, AuthStore, create_pkce_challenge

RFC7636_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC7636_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class FakeTokenTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_form(self, url, data):
        self.calls.append((url, data.copy()))
        return self.responses.pop(0)


class OpenAICodexOAuthTests(unittest.TestCase):
    def test_pkce_challenge_matches_rfc_example(self):
        self.assertEqual(create_pkce_challenge(RFC7636_VERIFIER), RFC7636_CHALLENGE)

    def test_login_session_builds_authorization_url(self):
        client = OpenAICodexOAuthClient()
        session = client.create_login_session(
            49152,
            state="state-123",
            verifier=RFC7636_VERIFIER,
        )

        parsed = urllib.parse.urlparse(session.authorization_url)
        query = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(session.provider_id, "openai-codex")
        self.assertEqual(session.state, "state-123")
        self.assertEqual(session.challenge, RFC7636_CHALLENGE)
        self.assertEqual(query["client_id"], [DEFAULT_CLIENT_ID])
        self.assertEqual(query["code_challenge"], [RFC7636_CHALLENGE])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["redirect_uri"], [session.redirect_uri])
        self.assertEqual(query["scope"], ["api codex"])

    def test_state_mismatch_rejected(self):
        client = OpenAICodexOAuthClient()
        session = client.create_login_session(49152, state="expected", verifier=RFC7636_VERIFIER)

        with self.assertRaises(OAuthStateMismatch):
            client.extract_authorization_code(
                f"{session.redirect_uri}?code=auth-code&state=wrong",
                session,
            )

    def test_loopback_server_receives_callback_code(self):
        try:
            server_context = LoopbackOAuthServer()
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EPERM}:
                self.skipTest(f"loopback bind is not permitted in this environment: {exc}")
            raise

        with server_context as server:
            with urllib.request.urlopen(
                f"{server.redirect_uri}?code=auth-code&state=ok",
                timeout=2,
            ) as response:
                self.assertEqual(response.status, 200)

            result = server.wait(timeout_seconds=2)

        self.assertEqual(result.code, "auth-code")
        self.assertEqual(result.state, "ok")
        self.assertEqual(result.error, "")

    def test_exchange_code_uses_mock_transport(self):
        transport = FakeTokenTransport(
            [
                {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "api codex",
                }
            ]
        )
        client = OpenAICodexOAuthClient(transport=transport)
        session = client.create_login_session(49152, state="state", verifier=RFC7636_VERIFIER)

        record = client.exchange_code(session, "auth-code", now=1000)

        self.assertEqual(record.provider_id, "openai-codex")
        self.assertEqual(record.access_token, "access-1")
        self.assertEqual(record.refresh_token, "refresh-1")
        self.assertEqual(record.expires_at, 4600)
        self.assertEqual(record.metadata["token_type"], "Bearer")
        _, data = transport.calls[0]
        self.assertEqual(data["grant_type"], "authorization_code")
        self.assertEqual(data["code"], "auth-code")
        self.assertEqual(data["code_verifier"], RFC7636_VERIFIER)
        self.assertEqual(data["redirect_uri"], session.redirect_uri)

    def test_refresh_if_needed_updates_expired_store(self):
        transport = FakeTokenTransport(
            [
                {
                    "access_token": "access-2",
                    "expires_in": 300,
                }
            ]
        )
        client = OpenAICodexOAuthClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            store = AuthStore(Path(tmp) / "auth.json")
            store.put(
                AuthRecord(
                    provider_id="openai-codex",
                    access_token="access-1",
                    refresh_token="refresh-1",
                    expires_at=1000,
                )
            )

            refreshed = client.refresh_if_needed(store, skew_seconds=120, now=950)

            self.assertEqual(refreshed.access_token, "access-2")
            self.assertEqual(refreshed.refresh_token, "refresh-1")
            self.assertEqual(refreshed.expires_at, 1250)
            self.assertEqual(store.get("openai-codex").access_token, "access-2")

        _, data = transport.calls[0]
        self.assertEqual(data["grant_type"], "refresh_token")
        self.assertEqual(data["refresh_token"], "refresh-1")

    def test_logout_clears_oauth_record(self):
        client = OpenAICodexOAuthClient()
        with tempfile.TemporaryDirectory() as tmp:
            store = AuthStore(Path(tmp) / "auth.json")
            store.put(AuthRecord(provider_id="openai-codex", access_token="access-1"))

            client.logout(store)

            self.assertIsNone(store.get("openai-codex"))


if __name__ == "__main__":
    unittest.main()
