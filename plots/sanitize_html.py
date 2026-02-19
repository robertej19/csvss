from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


# ----------------------------
# Sanitizer policy (allowlist)
# ----------------------------
DEFAULT_ALLOWED_TAGS = {
    # structure
    "div", "span",
    # emphasis
    "b", "strong", "i", "em",
    # code-ish
    "code", "pre",
    # lists
    "ul", "ol", "li",
    # misc
    "br",
}

# Drop the entire element AND its content (prevents hidden payloads)
DROP_CONTENT_TAGS = {
    "script", "style", "iframe", "object", "embed", "svg", "math",
    "form", "input", "button", "select", "option", "textarea",
    "meta", "link", "base",
    "audio", "video", "source",
    "img",   # tracking beacons / exfil via URL
}

# Only allow "class" by default (no href/src/style/on*)
DEFAULT_ALLOWED_ATTRS: Mapping[str, set[str]] = {
    "*": {"class"},
}

# Very conservative classname filter
CLASS_RE = re.compile(r"^[a-zA-Z0-9_\- ]*$")


def sanitize_html(
    raw: str,
    allowed_tags: Iterable[str] = DEFAULT_ALLOWED_TAGS,
    allowed_attrs: Mapping[str, set[str]] = DEFAULT_ALLOWED_ATTRS,
) -> str:
    """
    Sanitizes HTML using a strict allowlist:
      - only allowed tags are emitted
      - only allowed attributes are emitted (default: class)
      - dangerous tags are dropped (some with contents)
      - all text is escaped

    Safe for rendering inside SharePoint-hosted static HTML reports.
    """

    class _Sanitizer(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.out: list[str] = []
            self.allowed_tags = {t.lower() for t in allowed_tags}
            self.allowed_attrs = {k.lower(): {a.lower() for a in v} for k, v in allowed_attrs.items()}
            self.drop_content_stack: list[str] = []

        def _attrs_allowed_for(self, tag: str) -> set[str]:
            tag = tag.lower()
            base = set(self.allowed_attrs.get("*", set()))
            base |= set(self.allowed_attrs.get(tag, set()))
            return base

        def _emit_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            tag = tag.lower()
            attrs_allowed = self._attrs_allowed_for(tag)

            safe_attrs: list[str] = []
            for k, v in attrs:
                if v is None:
                    continue
                k = k.lower()

                # allow only allowlisted attrs
                if k not in attrs_allowed:
                    continue

                if k == "class":
                    v2 = v.strip()
                    if not v2:
                        continue
                    if not CLASS_RE.match(v2):
                        continue
                    safe_attrs.append(f' class="{escape(v2, quote=True)}"')
                else:
                    safe_attrs.append(f' {k}="{escape(v, quote=True)}"')

            self.out.append(f"<{tag}{''.join(safe_attrs)}>")

        def _emit_end(self, tag: str) -> None:
            tag = tag.lower()
            if tag in self.allowed_tags:
                self.out.append(f"</{tag}>")

        # ---- parser hooks ----
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            tag_l = tag.lower()

            # if dropping content, ignore until stack unwinds
            if self.drop_content_stack:
                if tag_l in DROP_CONTENT_TAGS:
                    self.drop_content_stack.append(tag_l)
                return

            # drop element + its content
            if tag_l in DROP_CONTENT_TAGS:
                self.drop_content_stack.append(tag_l)
                return

            # allowed tag
            if tag_l in self.allowed_tags:
                self._emit_start(tag_l, attrs)

        def handle_endtag(self, tag: str) -> None:
            tag_l = tag.lower()

            if self.drop_content_stack:
                if tag_l == self.drop_content_stack[-1]:
                    self.drop_content_stack.pop()
                return

            if tag_l in self.allowed_tags:
                self._emit_end(tag_l)

        def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            tag_l = tag.lower()

            if self.drop_content_stack:
                return
            if tag_l in DROP_CONTENT_TAGS:
                return

            if tag_l in self.allowed_tags:
                if tag_l == "br":
                    self.out.append("<br>")
                else:
                    self._emit_start(tag_l, attrs)
                    self._emit_end(tag_l)

        def handle_data(self, data: str) -> None:
            if self.drop_content_stack:
                return
            self.out.append(escape(data, quote=False))

        def handle_entityref(self, name: str) -> None:
            if self.drop_content_stack:
                return
            self.out.append(f"&{escape(name)};")

        def handle_charref(self, name: str) -> None:
            if self.drop_content_stack:
                return
            self.out.append(f"&#{escape(name)};")

        def handle_comment(self, data: str) -> None:
            # drop comments
            return

    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""

    p = _Sanitizer()
    p.feed(str(raw))
    p.close()
    return "".join(p.out)


# ----------------------------
# CSV sanitizer
# ----------------------------
@dataclass
class SanitizeReport:
    rows_total: int
    rows_changed: int
    chars_before: int
    chars_after: int


def sanitize_csv(
    in_path: Path,
    out_path: Path,
    html_col: str = "note_html",
) -> SanitizeReport:
    df = pd.read_csv(in_path)

    if html_col not in df.columns:
        raise SystemExit(f"Missing required column '{html_col}' in {in_path}")

    before = df[html_col].fillna("").astype(str)
    after = before.map(sanitize_html)

    rows_changed = int((before != after).sum())
    df[html_col] = after

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    return SanitizeReport(
        rows_total=len(df),
        rows_changed=rows_changed,
        chars_before=int(before.map(len).sum()),
        chars_after=int(after.map(len).sum()),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Sanitize note_html in a CSV for safe HTML report rendering.")
    ap.add_argument("--in", dest="in_path", default="data/data.csv", help="Input CSV (default: data/data.csv)")
    ap.add_argument("--out", dest="out_path", default="data/data.sanitized.csv", help="Output CSV")
    ap.add_argument("--col", dest="html_col", default="note_html", help="HTML column to sanitize")
    ap.add_argument("--inplace", action="store_true", help="Overwrite input file (sets --out = --in)")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    if args.inplace:
        out_path = in_path

    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    rep = sanitize_csv(in_path=in_path, out_path=out_path, html_col=args.html_col)

    print(f"Sanitized: {in_path} -> {out_path}")
    print(f"Rows: {rep.rows_total:,} | Changed: {rep.rows_changed:,}")
    print(f"Chars: {rep.chars_before:,} -> {rep.chars_after:,}")


if __name__ == "__main__":
    main()
