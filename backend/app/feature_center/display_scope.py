"""One policy for default rendered feature extent and reverse selection."""

from __future__ import annotations

from typing import Any


DEFAULT_RENDER_ROLES = frozenset({
    "wall", "body_wall", "head_wall", "bottom", "drill_tip", "step_transition",
    "transition", "top", "side_wall", "cavity_wall", "cavity_bottom",
    "rib_web", "flange_web", "boss_top", "boss_wall",
})


def is_default_render_link(link: dict[str, Any]) -> bool:
    """Support and measurement faces remain evidence, not feature body."""
    return str(link.get("role") or "") in DEFAULT_RENDER_ROLES
