"""Convert successful task summaries into reviewed memory SOP drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from generic_agent_engineered.memory import MemoryEntry, MemoryIndex, MemoryWriteRequest
from generic_agent_engineered.memory.index import normalize_title, slugify

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class StructuredTaskSummary:
    title: str
    objective: str
    outcome: str
    successful: bool
    steps: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    pitfalls: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SOPDraft:
    title: str
    slug: str
    content: str
    tags: tuple[str, ...]

    def to_memory_request(
        self,
        *,
        approved: bool = False,
        reviewer: str = "",
        source: str = "skill-crystallizer",
    ) -> MemoryWriteRequest:
        return MemoryWriteRequest(
            layer="L3",
            title=self.title,
            content=self.content,
            tags=self.tags,
            approved=approved,
            reviewer=reviewer,
            source=source,
        )


@dataclass(frozen=True)
class DuplicateSkill:
    entry: MemoryEntry
    reason: str
    score: float


class SkillCrystallizer:
    """Generate compact SOP drafts from verified successful tasks."""

    def __init__(self, *, duplicate_threshold: float = 0.72) -> None:
        self.duplicate_threshold = duplicate_threshold

    def generate_sop_draft(self, summary: StructuredTaskSummary) -> SOPDraft:
        if not summary.successful:
            raise ValueError("only successful tasks can be crystallized into SOP drafts")
        if not summary.title.strip():
            raise ValueError("summary title is required")
        if not summary.outcome.strip():
            raise ValueError("summary outcome is required")

        title = _sop_title(summary.title)
        sections = [
            f"# {title}",
            "",
            f"**Trigger**: {summary.objective.strip() or summary.title.strip()}",
            f"**Outcome**: {summary.outcome.strip()}",
        ]
        sections.extend(_section("Steps", summary.steps))
        sections.extend(_section("Tools", summary.tools))
        sections.extend(_section("Pitfalls", summary.pitfalls))
        sections.extend(_section("Verification", summary.verification))
        sections.extend(_section("Artifacts", summary.artifacts))
        content = "\n".join(sections).rstrip() + "\n"
        tags = tuple(dict.fromkeys((*summary.tags, "sop", "crystallized")))
        return SOPDraft(title=title, slug=slugify(title), content=content, tags=tags)

    def find_duplicate(self, draft: SOPDraft, index: MemoryIndex) -> DuplicateSkill | None:
        draft_title = normalize_title(draft.title)
        draft_tokens = set(_tokens(draft.title))
        draft_content_tokens = set(_tokens(draft.content))
        for entry in index.by_layer("L3"):
            if normalize_title(entry.title) == draft_title:
                return DuplicateSkill(entry=entry, reason="title", score=1.0)
            if entry.relative_path and entry.relative_path == f"{draft.slug}.md":
                return DuplicateSkill(entry=entry, reason="path", score=1.0)

            title_score = _jaccard(draft_tokens, set(_tokens(entry.title)))
            content_score = _jaccard(draft_content_tokens, set(_tokens(entry.content)))
            score = max(title_score, content_score)
            if score >= self.duplicate_threshold:
                return DuplicateSkill(entry=entry, reason="similarity", score=score)
        return None


def _sop_title(title: str) -> str:
    cleaned = title.strip()
    return cleaned if cleaned.lower().endswith("sop") else f"{cleaned} SOP"


def _section(name: str, values: tuple[str, ...]) -> list[str]:
    cleaned = tuple(value.strip() for value in values if value.strip())
    if not cleaned:
        return []
    lines = ["", f"## {name}"]
    lines.extend(f"- {value}" for value in cleaned)
    return lines


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token.lower() for token in TOKEN_RE.findall(value))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
