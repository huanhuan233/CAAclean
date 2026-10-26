# 统一默认高亮和反向选择的面角色白名单，支撑面与测量参考面不扩入特征显示范围。
"""One policy for default rendered feature extent and reverse selection."""

from __future__ import annotations

from typing import Any


DEFAULT_RENDER_ROLES = frozenset({
    "wall", "body_wall", "head_wall", "bottom", "drill_tip", "step_transition",
    "transition", "top", "side_wall", "cavity_wall", "cavity_bottom",
    "rib_web", "web_side", "flange_web", "boss_top", "boss_wall",
})


# 按面角色判断是否纳入默认显示和选择范围，返回值不改变该面的证据关联。
def is_default_render_link(link: dict[str, Any]) -> bool:
    """Support and measurement faces remain evidence, not feature body."""
    return str(link.get("role") or "") in DEFAULT_RENDER_ROLES
