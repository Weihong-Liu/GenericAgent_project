"""Read-only external integration status surfaces."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

from generic_agent_engineered.cli.bridge import _resolve_extension_dir, _resolve_legacy_dir
from generic_agent_engineered.engine import AgentRuntime

BRIDGE_HTTP_PORT = 18766


@dataclass(frozen=True)
class IntegrationStatus:
    name: str
    label: str
    status: str
    available: bool
    detail: str
    action: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "label": self.label,
            "status": self.status,
            "available": self.available,
            "detail": self.detail,
            "action": self.action,
        }


def list_integration_statuses(runtime: AgentRuntime) -> list[IntegrationStatus]:
    """Return free-code parity integration states without claiming wired support."""

    return [
        _ide_status(runtime),
        _desktop_status(),
        _chrome_status(),
        _voice_status(),
        _remote_status(),
        _mobile_status(),
        _teleport_status(),
    ]


def integration_status(runtime: AgentRuntime, name: str) -> IntegrationStatus:
    normalized = name.strip().lower()
    for item in list_integration_statuses(runtime):
        if item.name == normalized:
            return item
    raise ValueError(f"unknown integration: {name}")


def _ide_status(runtime: AgentRuntime) -> IntegrationStatus:
    workspace = getattr(runtime.settings, "workspace_root", None)
    root = workspace if isinstance(workspace, Path) else Path.cwd()
    return IntegrationStatus(
        name="ide",
        label="IDE",
        status="unavailable",
        available=False,
        detail=f"workspace detected at {root}",
        action="IDE selection and open-in-editor bridges are not wired yet.",
    )


def _desktop_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="desktop",
        label="Desktop app",
        status="unavailable",
        available=False,
        detail="no packaged desktop companion is registered",
        action="Install packaging/runtime support before enabling desktop handoff.",
    )


def _chrome_status() -> IntegrationStatus:
    extension_dir = _resolve_extension_dir()
    manifest = extension_dir / "manifest.json"
    legacy_dir = _resolve_legacy_dir()
    bridge_running = _port_in_use(BRIDGE_HTTP_PORT)
    available = manifest.is_file() and legacy_dir is not None
    if bridge_running:
        status = "connected"
    elif available:
        status = "available"
    elif manifest.is_file():
        status = "partial"
    else:
        status = "unavailable"

    detail_parts = [
        f"extension={'present' if manifest.is_file() else 'missing'}",
        f"legacy_bridge={'present' if legacy_dir is not None else 'missing'}",
        f"http_port={'listening' if bridge_running else 'closed'}",
    ]
    return IntegrationStatus(
        name="chrome",
        label="Chrome bridge",
        status=status,
        available=available,
        detail=", ".join(detail_parts),
        action=(
            "Run `gae bridge` or launch the TUI gateway with bridge extras installed."
            if available and not bridge_running
            else "Load the bundled Chrome extension and keep the bridge process running."
            if bridge_running
            else "Check out legacy GenericAgent next to ga_engineered or set GA_LEGACY_BRIDGE_DIR."
        ),
    )


def _voice_status() -> IntegrationStatus:
    configured = bool(os.environ.get("GA_VOICE_COMMAND"))
    return IntegrationStatus(
        name="voice",
        label="Voice input",
        status="configured" if configured else "unavailable",
        available=False,
        detail="GA_VOICE_COMMAND is set" if configured else "no capture/STT backend configured",
        action="Voice capture is not wired into the prompt pipeline yet.",
    )


def _remote_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="remote",
        label="Remote session",
        status="unavailable",
        available=False,
        detail="no remote session server is registered",
        action="Remote-control sessions are not implemented in ga_engineered yet.",
    )


def _mobile_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="mobile",
        label="Mobile handoff",
        status="unavailable",
        available=False,
        detail="no mobile companion endpoint is registered",
        action="Mobile handoff is not implemented in ga_engineered yet.",
    )


def _teleport_status() -> IntegrationStatus:
    return IntegrationStatus(
        name="teleport",
        label="Teleport",
        status="unavailable",
        available=False,
        detail="no teleport transport is registered",
        action="Repository teleport and remote mismatch flows are not implemented yet.",
    )


def _port_in_use(port: int, *, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()
