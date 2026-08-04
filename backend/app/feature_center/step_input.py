"""STEP 输入的只读检查、单位确认和坐标变换契约。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


class StepInputError(ValueError):
    """表示在调用 FreeCAD 前即可确定的文档级 STEP 输入错误。"""


@dataclass(frozen=True)
class StepInputInfo:
    """保存 STEP 文件追溯信息及源单位到 FreeCAD 毫米坐标的显式变换。"""

    file_name: str
    size_bytes: int
    sha256: str
    step_schema: str
    source_unit: str
    kernel_unit: str
    source_to_kernel_scale: float
    source_to_kernel_transform: list[list[float]]


# 用途：建立统一缩放的四阶齐次矩阵；平移保持为零，禁止隐藏经验补偿。
def _scale_transform(scale: float) -> list[list[float]]:
    return [
        [scale, 0.0, 0.0, 0.0],
        [0.0, scale, 0.0, 0.0],
        [0.0, 0.0, scale, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


# 用途：从 STEP 明文实体中识别本轮可验证的长度单位；未知单位必须显式失败。
def _read_length_unit(text: str) -> tuple[str, float]:
    normalized = re.sub(r"\s+", "", text).upper()
    if "SI_UNIT(.MILLI.,.METRE.)" in normalized:
        return "mm", 1.0
    if "SI_UNIT($,.METRE.)" in normalized or "SI_UNIT(,.METRE.)" in normalized:
        return "m", 1000.0
    if "CONVERSION_BASED_UNIT('INCH'" in normalized or 'CONVERSION_BASED_UNIT("INCH"' in normalized:
        return "in", 25.4
    raise StepInputError("STEP_UNIT_UNKNOWN：无法从 STEP 实体确认长度单位")


# 用途：只读检查 STEP Header、哈希和单位，并返回传给 B-Rep 阶段的可信元数据。
def inspect_step_input(path: Path | str) -> StepInputInfo:
    source = Path(path)
    if not source.is_file():
        raise StepInputError(f"STEP_INPUT_NOT_FOUND：{source.name}")
    content = source.read_bytes()
    text = content.decode("latin-1", errors="replace")
    if "ISO-10303-21" not in text[:4096].upper():
        raise StepInputError("STEP_HEADER_INVALID：缺少 ISO-10303-21 文件头")
    schema_match = re.search(
        r"FILE_SCHEMA\s*\(\s*\(\s*['\"]([^'\"]+)['\"]",
        text,
        flags=re.IGNORECASE,
    )
    if not schema_match:
        raise StepInputError("STEP_SCHEMA_UNKNOWN：FILE_SCHEMA 不可用")
    source_unit, scale = _read_length_unit(text)
    return StepInputInfo(
        file_name=source.name,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        step_schema=schema_match.group(1),
        source_unit=source_unit,
        kernel_unit="mm",
        source_to_kernel_scale=scale,
        source_to_kernel_transform=_scale_transform(scale),
    )
