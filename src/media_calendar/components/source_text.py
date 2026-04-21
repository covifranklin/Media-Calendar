"""Helpers for normalizing fetched source content into clean text."""

from __future__ import annotations

from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._ignore_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._ignore_depth:
            self._ignore_depth -= 1

    def handle_data(self, data):
        if self._ignore_depth:
            return
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def extract_source_text(body: str, *, content_type: str | None = None) -> str:
    """Normalize fetched source content into clean text for later processing."""

    if not body:
        return ""

    normalized_type = (content_type or "").lower()
    looks_like_html = (
        "html" in normalized_type
        or "xml" in normalized_type
        or "<html" in body.lower()
        or "<body" in body.lower()
    )

    if looks_like_html:
        extractor = _HTMLTextExtractor()
        extractor.feed(body)
        return extractor.get_text()

    lines = [" ".join(line.split()) for line in body.splitlines()]
    return "\n".join(line for line in lines if line)
