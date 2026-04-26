"""Browser bridge abstractions."""

from .cdp_bridge import (
    BrowserBridge,
    BrowserExecution,
    BrowserSession,
    BrowserSessionError,
    BrowserSessionStore,
    CdpBridge,
    TmWebDriverBridge,
    normalize_execute_result,
)
from .html_simplifier import SimplifiedHtml, simplify_html, truncate_with_budget

__all__ = [
    "BrowserBridge",
    "BrowserExecution",
    "BrowserSession",
    "BrowserSessionError",
    "BrowserSessionStore",
    "CdpBridge",
    "SimplifiedHtml",
    "TmWebDriverBridge",
    "normalize_execute_result",
    "simplify_html",
    "truncate_with_budget",
]
