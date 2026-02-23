"""Public API: figure factory and conveniences."""

from __future__ import annotations

from typing import Optional

from cssplt.core.figure import Figure
from cssplt.core.state import StateRegistry


def figure(state: Optional[StateRegistry] = None) -> Figure:
    """Return a new Figure.

    ``state`` may be a shared StateRegistry instance. If omitted, a new
    empty registry is created inside the Figure.
    """
    return Figure(state=state)


# Expose so callers can do: from cssplt import plt; plt.figure()
plt = type("plt", (), {"figure": staticmethod(figure)})()
