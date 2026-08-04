"""FreeCAD 解析脚本与后端测试共用的包围盒校验。"""

from __future__ import annotations

import math


KERNEL_INFINITY_SENTINEL_LIMIT = 1e90


# 用途：拒绝 OpenCascade 无限基准轴产生的 ±1e100 哨兵值，只保留有限几何范围。
def is_usable_bbox(box: dict | None) -> bool:
    if not box:
        return False
    values = list(box.get("min", [])) + list(box.get("max", []))
    return len(values) == 6 and all(
        math.isfinite(float(value)) and abs(float(value)) < KERNEL_INFINITY_SENTINEL_LIMIT
        for value in values
    )


# 用途：合并全部有效几何范围；无限基准轴或损坏范围不会污染模型包围盒。
def union_bbox(boxes: list[dict]) -> dict | None:
    usable = [box for box in boxes if is_usable_bbox(box)]
    if not usable:
        return None
    return {
        "min": [min(box["min"][axis] for box in usable) for axis in range(3)],
        "max": [max(box["max"][axis] for box in usable) for axis in range(3)],
    }
