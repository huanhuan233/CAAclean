# 定义图纸接口数据及像素/归一化坐标约束，统一使用左上和右下四元边界框。
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


REGION_TYPES = {
    "whole_page",
    "product_information",
    "dimension_diagram",
    "parameter_table",
    "title_block",
    "notes",
    "legend",
    "unknown",
}


# 图纸流程业务异常，错误码供 HTTP 层和任务状态使用。
class DrawingError(Exception):
    # 保存可公开的错误码与消息，同时初始化标准异常文本。
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# 转换为整数坐标并要求框有正面积且完全位于图像内。
def validate_bbox_pixels(bbox: list[int], *, width: int, height: int) -> list[int]:
    if len(bbox) != 4:
        raise DrawingError("layout_regions_invalid", "bbox must contain four values")
    x_min, y_min, x_max, y_max = [int(value) for value in bbox]
    if not (0 <= x_min < x_max <= width and 0 <= y_min < y_max <= height):
        raise DrawingError("layout_regions_invalid", "bbox is outside image bounds")
    return [x_min, y_min, x_max, y_max]


# 验证四个比例坐标位于 0 到 1 且左右、上下严格有序。
def validate_bbox_normalized(bbox: list[float]) -> list[float]:
    if len(bbox) != 4:
        raise DrawingError("layout_regions_invalid", "normalized bbox must contain four values")
    x_min, y_min, x_max, y_max = [float(value) for value in bbox]
    if not (0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1):
        raise DrawingError("layout_regions_invalid", "normalized bbox is outside image bounds")
    return [x_min, y_min, x_max, y_max]


# 先校验像素框，再按图像宽高分别归一化横纵坐标。
def bbox_pixels_to_normalized(bbox: list[int], *, width: int, height: int) -> list[float]:
    x_min, y_min, x_max, y_max = validate_bbox_pixels(bbox, width=width, height=height)
    return [x_min / width, y_min / height, x_max / width, y_max / height]


# 将比例框四舍五入为像素框，再检查是否因舍入变为无效区域。
def bbox_normalized_to_pixels(bbox: list[float], *, width: int, height: int) -> list[int]:
    x_min, y_min, x_max, y_max = validate_bbox_normalized(bbox)
    return validate_bbox_pixels(
        [
            round(x_min * width),
            round(y_min * height),
            round(x_max * width),
            round(y_max * height),
        ],
        width=width,
        height=height,
    )


# 接收人工框选类别及相对于原图的归一化坐标。
class ManualRegionIn(BaseModel):
    region_type: str
    bbox_normalized: list[float]
    confidence: float | None = None

    # 人工区域只允许预定义类别，禁止使用系统保留的 whole_page。
    @field_validator("region_type")
    @classmethod
    def validate_region_type(cls, value: str) -> str:
        if value not in REGION_TYPES - {"whole_page"}:
            raise ValueError("unsupported region type")
        return value

    # 对人工提交的归一化框复用统一边界验证。
    @field_validator("bbox_normalized")
    @classmethod
    def validate_bbox(cls, value: list[float]) -> list[float]:
        return validate_bbox_normalized(value)


# 要求人工更新至少提交一个区域。
class ManualRegionsIn(BaseModel):
    regions: list[ManualRegionIn] = Field(min_length=1)


# 返回任务标识、关联模型修订及当前状态。
class DrawingTaskOut(BaseModel):
    task_id: uuid.UUID
    revision_id: uuid.UUID | None = None
    status: str


# 表示版面流程状态及最近业务错误。
class DrawingLayoutStatusOut(BaseModel):
    task_id: uuid.UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None


# 向客户端提供裁剪区域坐标、文件摘要、尺寸及来源信息。
class DrawingRegionOut(BaseModel):
    id: uuid.UUID
    region_type: str
    bbox_normalized: list[float]
    bbox_pixels: list[int]
    padded_bbox_pixels: list[int]
    crop_sha256: str | None = None
    crop_width: int | None = None
    crop_height: int | None = None
    provider: str
    confidence: float | None = None


# 包装有效区域列表与数量。
class DrawingRegionListOut(BaseModel):
    items: list[DrawingRegionOut]
    total: int


# 保存原图和推理图尺寸、路径、摘要及双向缩放系数。
@dataclass
class PreprocessResult:
    original_path: Path
    inference_path: Path
    original_width: int
    original_height: int
    inference_width: int
    inference_height: int
    original_sha256: str
    inference_sha256: str
    scale_original_to_inference_x: float
    scale_original_to_inference_y: float
    scale_inference_to_original_x: float
    scale_inference_to_original_y: float

    # 验证原图框后按各轴缩放系数转换为推理图像素。
    def original_to_inference_bbox(self, bbox: list[int]) -> list[int]:
        x_min, y_min, x_max, y_max = validate_bbox_pixels(bbox, width=self.original_width, height=self.original_height)
        return [
            round(x_min * self.scale_original_to_inference_x),
            round(y_min * self.scale_original_to_inference_y),
            round(x_max * self.scale_original_to_inference_x),
            round(y_max * self.scale_original_to_inference_y),
        ]

    # 将推理图框映回原图，并复查舍入后的原图边界。
    def inference_to_original_bbox(self, bbox: list[int]) -> list[int]:
        x_min, y_min, x_max, y_max = validate_bbox_pixels(bbox, width=self.inference_width, height=self.inference_height)
        return validate_bbox_pixels(
            [
                round(x_min * self.scale_inference_to_original_x),
                round(y_min * self.scale_inference_to_original_y),
                round(x_max * self.scale_inference_to_original_x),
                round(y_max * self.scale_inference_to_original_y),
            ],
            width=self.original_width,
            height=self.original_height,
        )

    # 输出后续组装裁剪包所需的尺寸和坐标缩放元数据。
    def metadata(self) -> dict:
        return {
            "original_width": self.original_width,
            "original_height": self.original_height,
            "inference_width": self.inference_width,
            "inference_height": self.inference_height,
            "scale_original_to_inference_x": self.scale_original_to_inference_x,
            "scale_original_to_inference_y": self.scale_original_to_inference_y,
            "scale_inference_to_original_x": self.scale_inference_to_original_x,
            "scale_inference_to_original_y": self.scale_inference_to_original_y,
        }


# 为视觉提取打包原图信息、全页推理图、有效裁剪区域及版面状态。
class DrawingCropPackage(BaseModel):
    schema_version: Literal["drawing_crop_v1"] = "drawing_crop_v1"
    task_id: uuid.UUID
    source_id: uuid.UUID
    original_image: dict
    inference_image: dict
    layout: dict
    regions: list[dict]
    warnings: list[str] = Field(default_factory=list)
