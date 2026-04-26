"""Small, dependency-free HTML simplification for browser scans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser

DROP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "meta", "link"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "source", "track", "wbr"}
ALLOWED_ATTRS = {
    "id",
    "class",
    "role",
    "aria-label",
    "title",
    "name",
    "type",
    "value",
    "placeholder",
    "href",
    "src",
    "alt",
    "for",
    "selected",
    "checked",
    "disabled",
    "data-testid",
    "data-test",
    "data-id",
}


@dataclass(frozen=True)
class SimplifiedHtml:
    content: str
    original_chars: int
    simplified_chars: int
    truncated: bool
    text_only: bool
    budget_chars: int


def simplify_html(
    raw_html: str,
    *,
    text_only: bool = False,
    max_chars: int = 35_000,
) -> SimplifiedHtml:
    budget = _positive_budget(max_chars)
    parser = _SimplifyingParser(text_only=text_only)
    parser.feed(raw_html)
    parser.close()
    simplified = parser.render()
    if text_only:
        simplified = _normalize_text(simplified)
    content, truncated = truncate_with_budget(simplified, budget)
    return SimplifiedHtml(
        content=content,
        original_chars=len(raw_html),
        simplified_chars=len(simplified),
        truncated=truncated,
        text_only=text_only,
        budget_chars=budget,
    )


def truncate_with_budget(
    value: str,
    max_chars: int,
    *,
    marker: str = "\n... [TRUNCATED]\n",
) -> tuple[str, bool]:
    budget = _positive_budget(max_chars)
    if len(value) <= budget:
        return value, False
    if budget <= len(marker):
        return value[:budget], True
    keep = budget - len(marker)
    head = keep // 2
    tail = keep - head
    return f"{value[:head].rstrip()}{marker}{value[-tail:].lstrip()}", True


class _SimplifyingParser(HTMLParser):
    def __init__(self, *, text_only: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.text_only = text_only
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag_name in DROP_TAGS or _is_hidden(attrs):
            if tag_name in VOID_TAGS:
                return
            self.skip_depth = 1
            return
        if self.text_only:
            return
        attr_text = _render_attrs(attrs)
        self.parts.append(f"<{tag_name}{attr_text}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if self.skip_depth or tag_name in DROP_TAGS or _is_hidden(attrs) or self.text_only:
            return
        attr_text = _render_attrs(attrs)
        self.parts.append(f"<{tag_name}{attr_text}>")

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if self.text_only or tag_name in DROP_TAGS or tag_name in VOID_TAGS:
            return
        self.parts.append(f"</{tag_name}>")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = _collapse_inline_space(data)
        if not text:
            return
        self.parts.append(text if self.text_only else escape(text, quote=False))

    def render(self) -> str:
        return "\n".join(self.parts) if self.text_only else "".join(self.parts)


def _render_attrs(attrs: list[tuple[str, str | None]]) -> str:
    rendered: list[str] = []
    for key, value in attrs:
        name = key.lower()
        if name not in ALLOWED_ATTRS:
            continue
        if value is None:
            rendered.append(name)
            continue
        collapsed = _collapse_inline_space(value)
        if not collapsed:
            continue
        rendered.append(f'{name}="{escape(collapsed, quote=True)}"')
    return f" {' '.join(rendered)}" if rendered else ""


def _is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
    attr_map = {key.lower(): value or "" for key, value in attrs}
    if "hidden" in attr_map:
        return True
    if attr_map.get("aria-hidden", "").lower() == "true":
        return True
    style = attr_map.get("style", "").replace(" ", "").lower()
    return any(
        marker in style
        for marker in (
            "display:none",
            "visibility:hidden",
            "opacity:0",
            "position:fixed",
            "position:sticky",
        )
    )


def _normalize_text(value: str) -> str:
    lines = [_collapse_inline_space(line) for line in value.splitlines()]
    lines = [line for line in lines if line]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _collapse_inline_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _positive_budget(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("max_chars must be an integer")
    if value < 1:
        raise ValueError("max_chars must be positive")
    return value
