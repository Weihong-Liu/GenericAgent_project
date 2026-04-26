"""Provider error mapping."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base error raised by provider clients."""

    def __init__(
        self,
        message: str,
        *,
        provider_id: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.status_code = status_code


class ProviderAuthError(ProviderError):
    """Authentication or authorization failure."""


class ProviderRateLimitError(ProviderError):
    """Provider rate limit failure."""


class ProviderServerError(ProviderError):
    """Provider 5xx failure."""


class ProviderProtocolError(ProviderError):
    """Provider response shape could not be normalized."""


def provider_error_from_status(
    status_code: int,
    message: str,
    *,
    provider_id: str = "",
) -> ProviderError:
    if status_code in {401, 403}:
        return ProviderAuthError(message, provider_id=provider_id, status_code=status_code)
    if status_code == 429:
        return ProviderRateLimitError(message, provider_id=provider_id, status_code=status_code)
    if status_code >= 500:
        return ProviderServerError(message, provider_id=provider_id, status_code=status_code)
    return ProviderError(message, provider_id=provider_id, status_code=status_code)


def map_provider_exception(exc: Exception, *, provider_id: str = "") -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc

    status_code = _status_code(exc)
    message = str(exc) or exc.__class__.__name__
    if status_code is not None:
        return provider_error_from_status(status_code, message, provider_id=provider_id)
    return ProviderError(message, provider_id=provider_id)


def _status_code(exc: Exception) -> int | None:
    raw_status = getattr(exc, "status_code", None)
    if isinstance(raw_status, int):
        return raw_status

    response = getattr(exc, "response", None)
    raw_status = getattr(response, "status_code", None)
    return raw_status if isinstance(raw_status, int) else None
