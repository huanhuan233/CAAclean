# 清理规格模板结构，避免把模板已有值误当作当前图纸的提取事实。
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal


# 结构模式仅保留版本与参数名，其他模式返回深拷贝；空模板返回空参数列表。
def sanitize_template_structure(template: dict[str, Any] | None, *, mode: Literal["structure_only", "field-template"] = "structure_only") -> dict[str, Any]:
    if not template:
        return {"parameters": []}
    if mode != "structure_only":
        return deepcopy(template)
    return {
        "schema_version": template.get("schema_version"),
        "template_mode": "skeleton",
        "parameters": [
            {"name": parameter["name"]}
            for parameter in template.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("name")
        ],
    }

