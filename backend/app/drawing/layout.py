# 统一版面区域表示、供应商标签映射及相邻同类区域合并规则。
from __future__ import annotations

from dataclasses import dataclass, field

from app.drawing.schemas import REGION_TYPES, DrawingError, validate_bbox_pixels


# 保存原始像素框、区域类别、来源与置信度，原始供应商结果用于追溯。
@dataclass
class LayoutRegion:
    region_type: str
    bbox_pixels: list[int]
    confidence: float | None
    provider: str
    provider_region_type: str | None = None
    raw_provider_result: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # 将不在允许集合中的区域类别归为 unknown。
    def __post_init__(self):
        if self.region_type not in REGION_TYPES:
            self.region_type = "unknown"

    # 按区域自身宽高比例向外扩边，并截断到图像边界。
    def padded_bbox(self, *, width: int, height: int, padding_ratio: float) -> list[int]:
        x_min, y_min, x_max, y_max = validate_bbox_pixels(self.bbox_pixels, width=width, height=height)
        pad_x = round((x_max - x_min) * padding_ratio)
        pad_y = round((y_max - y_min) * padding_ratio)
        return [
            max(0, x_min - pad_x),
            max(0, y_min - pad_y),
            min(width, x_max + pad_x),
            min(height, y_max + pad_y),
        ]


# 汇总版面检测状态、区域列表和降级警告。
@dataclass
class LayoutDetectionResult:
    provider: str
    provider_version: str | None
    status: str
    regions: list[LayoutRegion]
    warnings: list[str] = field(default_factory=list)
    raw_provider_result: dict = field(default_factory=dict)


# 映射表格、图像等标签；文本区域按页面纵向位置作启发式分类。
def provider_type_to_region_type(provider_type: str | None, bbox: list[int], *, image_width: int, image_height: int) -> str:
    value = (provider_type or "").lower()
    if value in {"table"}:
        return "parameter_table"
    if value in {"image", "figure"}:
        return "dimension_diagram"
    if value in {"title"}:
        return "title_block"
    if value in {"caption", "legend"}:
        return "legend"
    if value in {"text"}:
        _, y_min, _, y_max = bbox
        if y_max <= image_height * 0.2:
            return "product_information"
        if y_min >= image_height * 0.55:
            return "notes"
    return "unknown"


# 按类型和位置排序，合并间距阈值内的同类框；空结果和非法坐标报错。
def merge_regions(regions: list[LayoutRegion], *, image_width: int, image_height: int, gap_ratio: float) -> list[LayoutRegion]:
    if not regions:
        raise DrawingError("layout_no_regions", "layout provider returned no regions")
    gap_x = image_width * gap_ratio
    gap_y = image_height * gap_ratio
    pending = sorted(regions, key=lambda item: (item.region_type, item.bbox_pixels[1], item.bbox_pixels[0]))
    merged: list[LayoutRegion] = []
    for region in pending:
        validate_bbox_pixels(region.bbox_pixels, width=image_width, height=image_height)
        # 每个新区只合并到当前首个匹配框；这里不迭代求所有连通区域的闭包。
        target = next((item for item in merged if _should_merge(item, region, gap_x=gap_x, gap_y=gap_y)), None)
        if target is None:
            merged.append(region)
            continue
        target.bbox_pixels = _union(target.bbox_pixels, region.bbox_pixels)
        if target.confidence is not None and region.confidence is not None:
            target.confidence = max(target.confidence, region.confidence)
    return sorted(merged, key=lambda item: (item.bbox_pixels[1], item.bbox_pixels[0]))


# 要求区域类型相同且横纵方向都在允许间距内。
def _should_merge(left: LayoutRegion, right: LayoutRegion, *, gap_x: float, gap_y: float) -> bool:
    if left.region_type != right.region_type:
        return False
    a = left.bbox_pixels
    b = right.bbox_pixels
    horizontal_close = a[0] <= b[2] + gap_x and b[0] <= a[2] + gap_x
    vertical_close = a[1] <= b[3] + gap_y and b[1] <= a[3] + gap_y
    return horizontal_close and vertical_close


# 计算同时包围两个像素框的最小外接矩形。
def _union(left: list[int], right: list[int]) -> list[int]:
    return [min(left[0], right[0]), min(left[1], right[1]), max(left[2], right[2]), max(left[3], right[3])]
