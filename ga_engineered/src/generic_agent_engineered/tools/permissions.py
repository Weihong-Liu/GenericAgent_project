"""Permission and risk helpers for command-executing tools."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CommandRiskLevel = Literal["safe", "approval_required"]


@dataclass(frozen=True)
class CommandRisk:
    level: CommandRiskLevel
    reasons: tuple[str, ...] = ()

    @property
    def requires_approval(self) -> bool:
        return self.level == "approval_required"


@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    risk: CommandRisk
    approved_by_yolo: bool = False


@dataclass(frozen=True)
class ExecutionPolicy:
    yolo: bool = False


_DANGEROUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|[;&|\n]\s*)rm\s+-[A-Za-z]*[rR][A-Za-z]*f?\b"), "recursive remove"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "discard git working tree changes"),
    (re.compile(r"\bgit\s+clean\b[^;&|\n]*-[A-Za-z]*f"), "delete untracked git files"),
    (re.compile(r"\bgit\s+push\b[^;&|\n]*(--force|--force-with-lease|-f)\b"), "force push"),
    (re.compile(r"\bgit\s+checkout\s+(--\s+)?\."), "discard checkout of working tree"),
    (re.compile(r"\bgit\s+restore\s+(--\s+)?\."), "discard restore of working tree"),
    (re.compile(r"\bgit\s+stash\s+(drop|clear)\b"), "remove git stash data"),
    (re.compile(r"\bchmod\s+-R\s+777\b"), "recursive world-writable permissions"),
    (re.compile(r"\bchown\s+-R\b"), "recursive ownership change"),
    (re.compile(r"\bsudo\b"), "privileged command"),
    (re.compile(r"\bdd\s+.*\bof="), "raw block device or file overwrite"),
    (re.compile(r"\bmkfs(\.\w+)?\b"), "filesystem formatting"),
    (re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b"), "system shutdown"),
    (re.compile(r"\bkubectl\s+delete\b"), "delete Kubernetes resources"),
    (re.compile(r"\bterraform\s+destroy\b"), "destroy Terraform resources"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE), "drop database objects"),
    (
        re.compile(r"\bTRUNCATE\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
        "truncate database objects",
    ),
    (re.compile(r"\bDELETE\s+FROM\s+\w+\s*(;|$)", re.IGNORECASE), "unqualified database delete"),
    (
        re.compile(r"(curl|wget)\b[^|;&\n]*((?<!\|)\|(?!\|)|>\s*/tmp/|>\s*/var/tmp/)"),
        "download pipe or temp write",
    ),
)


def classify_shell_command(command: str) -> CommandRisk:
    if not isinstance(command, str) or not command.strip():
        return CommandRisk(level="approval_required", reasons=("empty command",))

    reasons = tuple(reason for pattern, reason in _DANGEROUS_PATTERNS if pattern.search(command))
    if reasons:
        return CommandRisk(level="approval_required", reasons=reasons)
    return CommandRisk(level="safe")


def decide_execution(command: str, policy: ExecutionPolicy) -> ExecutionDecision:
    risk = classify_shell_command(command)
    if risk.requires_approval and not policy.yolo:
        return ExecutionDecision(allowed=False, risk=risk)
    return ExecutionDecision(
        allowed=True,
        risk=risk,
        approved_by_yolo=risk.requires_approval and policy.yolo,
    )
