"""Convert untrusted Canvas HTML into bounded plain text for search and prompts."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = _TAG_RE.sub(" ", raw)
        return _WS_RE.sub(" ", raw).strip()


def html_to_plain_text(html: str | None, *, max_chars: int = 50_000) -> str:
    if not html or not html.strip():
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()[:max_chars]
    text = parser.text()
    if len(text) > max_chars:
        return f"{text[: max_chars - 1]}…"
    return text
