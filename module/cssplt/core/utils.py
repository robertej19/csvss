"""Shared utilities.

For Step 2 we provide a real ``esc()`` helper for HTML-escaping any
user-supplied string before inserting it into text nodes or attribute
values. This should be used for all labels, titles, and other content
that can come from data.
"""

from __future__ import annotations

import html
from typing import Any


def esc(value: Any) -> str:
    """Return an HTML-escaped string representation of *value*.

    This is intended for user/data-supplied strings. It escapes ``&``, ``<``,
    ``>``, and both single and double quotes so the result is safe for use
    in element text or attribute values.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)

