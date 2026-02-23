"""Interactive state primitives (Step 2).

StateRegistry owns a collection of interactive variables which are rendered
as HTML-only controls (radios / checkboxes). Each variable can also provide
CSS selector helpers that will later be used with ``:has()`` to filter and
switch pre-rendered plot variants.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Mapping, Sequence, Tuple

from .utils import esc


# Hard cap: if 2^num_tags > this, disable combinatorial tag views and only
# allow single-tag (plus empty) variants to avoid memory blow-up.
MAX_TAG_COMBINATIONS = 256


class TagFilterMode(str, Enum):
    """How to interpret multiple selected tags when filtering data.

    ANY:  match rows that have *any* of the selected tags (OR semantics).
    ALL:  match rows that have *all* of the selected tags (AND semantics).

    This is a coding-time option used by artists / renderers; it does not
    change the HTML controls themselves.
    """

    ANY = "any"
    ALL = "all"


def iter_tag_subsets(
    tag_values: List[str],
) -> List[Tuple[str, Tuple[str, ...]]]:
    """Yield (canonical_key, subset_tuple) for every subset of tag_values.

    Empty subset has key "empty"; others use ",".join(sorted(subset)).
    Order is deterministic (empty first, then by size, then lexicographic).
    """
    from itertools import combinations

    n = len(tag_values)
    out: List[Tuple[str, Tuple[str, ...]]] = [("empty", ())]
    for r in range(1, n + 1):
        for combo in combinations(tag_values, r):
            subset = tuple(sorted(combo))
            key = ",".join(subset)
            out.append((key, subset))
    return out


@dataclass(frozen=True)
class _Option:
    value: str
    label: str


def _normalize_options(
    options: Sequence[str] | Sequence[Tuple[str, str]] | Mapping[str, str],
) -> List[_Option]:
    """Normalize different option specifications into _Option objects.

    Accepts:
    - Sequence[str]: value and label are the same token
    - Sequence[(value, label)]
    - Mapping[value, label]

    Keys / values are treated as internal tokens (expected to be CSS/HTML
    safe already). Labels are user-facing and will be escaped via ``esc()``.
    """
    out: List[_Option] = []

    if isinstance(options, Mapping):
        for v, label in options.items():
            out.append(_Option(str(v), str(label)))
        return out

    for item in options:
        if isinstance(item, tuple) and len(item) == 2:
            v, label = item
            out.append(_Option(str(v), str(label)))
        else:
            out.append(_Option(str(item), str(item)))

    return out


@dataclass
class RadioVar:
    """Single-choice variable rendered as a group of radio buttons."""

    key: str
    options: List[_Option]
    default: str | None = None

    def html(self) -> str:
        """Return HTML for the radio inputs + pill labels."""
        parts: List[str] = []
        key = self.key
        parts.append(
            f'<div class="cssplt-control cssplt-control--radio" data-var-key="{key}">'
        )

        for opt in self.options:
            value = opt.value
            label = opt.label
            input_id = f"cssplt-{key}-{value}"
            checked = (
                ' checked="checked"'
                if (self.default is not None and value == self.default)
                else ""
            )
            parts.append(
                '  <input type="radio"'
                f' class="cssplt-input cssplt-input--radio"'
                f' id="{input_id}"'
                f' name="{key}"'
                f' value="{value}"'
                f' data-var-key="{key}"'
                f' data-var-value="{value}"{checked}>'
            )
            parts.append(
                f'  <label class="cssplt-pill" for="{input_id}">{esc(label)}</label>'
            )

        parts.append("</div>")
        return "\n".join(parts)

    def checked_selector(self, value: str, container: str = ".cssplt-fig") -> str:
        """Return a CSS selector that matches when *value* is selected.

        Example (default container)::

            .cssplt-fig:has(input[type="radio"][data-var-key="metric"][
                data-var-value="accuracy"]:checked)

        This will later be used to gate visibility of pre-rendered variants.
        """
        v = str(value)
        key = self.key
        return (
            f'{container}:has('
            f'input[type="radio"][data-var-key="{key}"][data-var-value="{v}"]:checked'
            f")"
        )


@dataclass
class MultiCheckVar:
    """Multi-select variable rendered as a group of checkboxes."""

    key: str
    options: List[_Option]
    filter_mode: TagFilterMode = TagFilterMode.ANY

    def html(self) -> str:
        """Return HTML for checkbox inputs + pill labels."""
        parts: List[str] = []
        key = self.key
        parts.append(
            f'<div class="cssplt-control cssplt-control--multi" data-var-key="{key}">'
        )

        for opt in self.options:
            value = opt.value
            label = opt.label
            input_id = f"cssplt-{key}-{value}"
            parts.append(
                '  <input type="checkbox"'
                f' class="cssplt-input cssplt-input--checkbox"'
                f' id="{input_id}"'
                f' name="{key}"'
                f' value="{value}"'
                f' data-var-key="{key}"'
                f' data-var-value="{value}">'
            )
            parts.append(
                f'  <label class="cssplt-pill" for="{input_id}">{esc(label)}</label>'
            )

        parts.append("</div>")
        return "\n".join(parts)

    def any_selected_selector(
        self, value: str, container: str = ".cssplt-fig"
    ) -> str:
        """Return selector that matches when *value* is among the selections."""
        v = str(value)
        key = self.key
        return (
            f'{container}:has('
            f'input[type="checkbox"][data-var-key="{key}"][data-var-value="{v}"]:checked'
            f")"
        )

    def subset_selector(
        self, active_values: Iterable[str], container: str = ".cssplt-fig"
    ) -> str:
        """Return selector for an exact subset of checked options.

        ``active_values`` is the set of values that must be checked; all
        other options belonging to this variable must be unchecked.
        An empty set expresses \"none selected\" for this variable.
        """
        active_set = {str(v) for v in active_values}
        all_values = {opt.value for opt in self.options}

        unknown = active_set - all_values
        if unknown:
            raise ValueError(f"Unknown values for {self.key}: {sorted(unknown)}")

        inactive_values = all_values - active_set

        parts: List[str] = [container]

        # Require all active ones to be checked.
        for v in sorted(active_set):
            parts.append(
                f':has(input[type="checkbox"][data-var-key="{self.key}"]'
                f'[data-var-value="{v}"]:checked)'
            )

        # And require all others to be unchecked.
        for v in sorted(inactive_values):
            parts.append(
                f':not(:has(input[type="checkbox"][data-var-key="{self.key}"]'
                f'[data-var-value="{v}"]:checked))'
            )

        return "".join(parts)

    def at_least_n_checked_selectors(
        self, n: int, container: str = ".cssplt-fig"
    ) -> List[str]:
        """Return selectors that match when at least n options are checked.

        One selector per n-combination of options. Used e.g. in ALL mode to
        show the empty variant when 2+ tags are selected.
        """
        from itertools import combinations

        values = [opt.value for opt in self.options]
        if n > len(values):
            return []
        result: List[str] = []
        for combo in combinations(values, n):
            parts = [container]
            for v in combo:
                parts.append(
                    f':has(input[type="checkbox"][data-var-key="{self.key}"]'
                    f'[data-var-value="{v}"]:checked)'
                )
            result.append("".join(parts))
        return result


class StateRegistry:
    """Owns interactive variables and renders their controls."""

    def __init__(
        self,
        tag_filter_mode: TagFilterMode | str = TagFilterMode.ANY,
    ) -> None:
        self._vars: List[RadioVar | MultiCheckVar] = []
        # File-level default for how tag multi-selects should be interpreted.
        if isinstance(tag_filter_mode, TagFilterMode):
            self.tag_filter_mode = tag_filter_mode
        else:
            self.tag_filter_mode = TagFilterMode(tag_filter_mode)

    # Public API -----------------------------------------------------
    def add_radio(
        self,
        key: str,
        options: Sequence[str] | Sequence[Tuple[str, str]] | Mapping[str, str],
        default: str | None = None,
    ) -> RadioVar:
        radio = RadioVar(key=key, options=_normalize_options(options), default=default)
        self._vars.append(radio)
        return radio

    def add_multi(
        self,
        key: str,
        options: Sequence[str] | Sequence[Tuple[str, str]] | Mapping[str, str],
        filter_mode: TagFilterMode | str | None = None,
    ) -> MultiCheckVar:
        mode = filter_mode or self.tag_filter_mode
        if not isinstance(mode, TagFilterMode):
            mode = TagFilterMode(mode)
        multi = MultiCheckVar(
            key=key,
            options=_normalize_options(options),
            filter_mode=mode,
        )
        self._vars.append(multi)
        return multi

    def render_html(self) -> str:
        """Return concatenated HTML for all registered controls."""
        return "\n".join(var.html() for var in self._vars)

