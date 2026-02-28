"""Sanitize rich HTML for note/tooltip fields. Allowlist of safe tags and attributes."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# Tags allowed in sanitized output (inline/safe only). No script, no form, no iframe.
ALLOWED_TAGS = frozenset({"b", "i", "em", "strong", "br", "span"})
# For span we allow only class (e.g. for styling). No href, onclick, style, etc.
ALLOWED_ATTRS = frozenset({"class"})
# Restrict class to alphanumeric and hyphen (no javascript: etc.)
SAFE_CLASS = re.compile(r"^[a-zA-Z0-9_\-\s]+$")


class _SanitizerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        if tag == "br":
            self._out.append("<br>")
            return
        parts = [f"<{tag}"]
        for k, v in attrs:
            k = k.lower()
            if k not in ALLOWED_ATTRS or v is None:
                continue
            if k == "class" and not SAFE_CLASS.match(v):
                continue
            parts.append(f' {k}="{html.escape(v, quote=True)}"')
        parts.append(">")
        self._out.append("".join(parts))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag != "br":
            self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._out.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        decoded = html.unescape("&" + name + ";")
        self._out.append(html.escape(decoded))

    def handle_charref(self, name: str) -> None:
        decoded = html.unescape("&#" + name + ";")
        self._out.append(html.escape(decoded))

    def get_result(self) -> str:
        return "".join(self._out)


def sanitize(html_input: str) -> str:
    """Return sanitized HTML safe for use in note/tooltip content.

    Allows only inline tags: b, i, em, strong, br, span. For span only
    the class attribute is allowed (and must match safe characters).
    All other tags and attributes are stripped; text and entities are escaped.
    """
    if not html_input or not html_input.strip():
        return ""
    parser = _SanitizerParser()
    try:
        parser.feed(html_input)
        return parser.get_result()
    except Exception:
        return html.escape(html_input)
