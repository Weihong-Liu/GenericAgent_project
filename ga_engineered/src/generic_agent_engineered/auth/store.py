"""Auth store and OAuth helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuthRecord:
    provider_id: str
    access_token: str = ""
    refresh_token: str = ""
    api_key: str = ""
    expires_at: float | None = None
    metadata: dict[str, Any] | None = None

    def is_expired(self, skew_seconds: int = 120) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - skew_seconds


class AuthStore:
    """Small JSON auth store with atomic writes."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, AuthRecord]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        records = data.get("providers", {})
        return {key: AuthRecord(**value) for key, value in records.items()}

    def get(self, provider_id: str) -> AuthRecord | None:
        return self.load_all().get(provider_id)

    def put(self, record: AuthRecord) -> None:
        records = self.load_all()
        records[record.provider_id] = record
        payload = {"version": 1, "providers": {k: asdict(v) for k, v in records.items()}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".auth.", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_name, self.path)
            with suppress(OSError):
                os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def delete(self, provider_id: str) -> None:
        records = self.load_all()
        records.pop(provider_id, None)
        payload = {"version": 1, "providers": {k: asdict(v) for k, v in records.items()}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def create_pkce_pair() -> tuple[str, str]:
    """Return `(verifier, challenge)` for OAuth PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")
    return verifier, create_pkce_challenge(verifier)


def create_pkce_challenge(verifier: str) -> str:
    """Return the RFC 7636 S256 challenge for a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
