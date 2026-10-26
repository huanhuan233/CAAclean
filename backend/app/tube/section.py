# 原生设计截面解释：只接受可信草图坐标系内的两条完整同心圆。
# 输出 nominal_wall_mm 是设计半径差，不能作为最终实体或实物壁厚的测量结论。

"""Interpret a captured native sweep sketch without claiming measured tube walls."""

from __future__ import annotations

import math
from typing import Any


# 输入为已采集草图及毫米容差；排除构造几何，核验整圆、同心和真实元素 ID。
# 任何必要证据缺失都返回 unsupported_profile 和空尺寸，不填默认管径。
def native_concentric_profile(sketch: dict[str, Any], tolerance_mm: float = 0.001) -> dict[str, Any]:
    """Return design profile dimensions only for two full concentric circles."""
    unknown = {"status": "unsupported_profile", "source": "native_sketch", "outer_diameter_mm": None,
               "inner_diameter_mm": None, "nominal_wall_mm": None}
    if sketch.get("axis", {}).get("status") != "verified_orthonormal":
        return unknown
    elements = sketch.get("elements") or []
    # 只接受明确标为非构造的元素；construction 缺失不能猜成实际轮廓。
    relevant = [item for item in elements if item.get("construction") is False]
    if len(relevant) != 2 or any(item.get("kind") != "circle" for item in relevant):
        return unknown
    circles = []
    for item in relevant:
        center = item.get("center_2d_mm")
        limits = item.get("parameter_range_raw")
        radius = item.get("radius_mm")
        if (not isinstance(center, list) or len(center) != 2 or
            not isinstance(limits, list) or len(limits) != 2 or
            isinstance(radius, bool) or not isinstance(radius, (int, float))):
            return unknown
        try:
            cx, cy = map(float, center)
            start, end = map(float, limits)
            radius = float(radius)
        except (ValueError, TypeError):
            return unknown
        if not all(map(math.isfinite, (cx, cy, start, end, radius))) or radius <= tolerance_mm:
            return unknown
        if abs(abs(end - start) - 2 * math.pi) > 1e-4:
            # 圆弧不是完整环形截面；参数范围的容差在此以弧度表达。
            return unknown
        circles.append((radius, cx, cy, str(item.get("element_id") or "")))
    outer, inner = sorted(circles, reverse=True)
    if (outer[0] - inner[0] <= tolerance_mm or
        math.hypot(outer[1] - inner[1], outer[2] - inner[2]) > tolerance_mm or
        not outer[3] or not inner[3]):
        return unknown
    return {"status": "native_profile_annulus", "source": "native_sketch",
            "outer_diameter_mm": 2 * outer[0], "inner_diameter_mm": 2 * inner[0],
            "nominal_wall_mm": outer[0] - inner[0], "center_2d_mm": [outer[1], outer[2]],
            "element_ids": [outer[3], inner[3]], "unit": "mm",
            "scope": "sweep_input_sketch_only;solid_wall_unverified"}
