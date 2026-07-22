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


class DrawingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_bbox_pixels(bbox: list[int], *, width: int, height: int) -> list[int]:
    if len(bbox) != 4:
        raise DrawingError("layout_regions_invalid", "bbox must contain four values")
    x_min, y_min, x_max, y_max = [int(value) for value in bbox]
    if not (0 <= x_min < x_max <= width and 0 <= y_min < y_max <= height):
        raise DrawingError("layout_regions_invalid", "bbox is outside image bounds")
    return [x_min, y_min, x_max, y_max]


def validate_bbox_normalized(bbox: list[float]) -> list[float]:
    if len(bbox) != 4:
        raise DrawingError("layout_regions_invalid", "normalized bbox must contain four values")
    x_min, y_min, x_max, y_max = [float(value) for value in bbox]
    if not (0 <= x_min < x_max <= 1 and 0 <= y_min < y_max <= 1):
        raise DrawingError("layout_regions_invalid", "normalized bbox is outside image bounds")
    return [x_min, y_min, x_max, y_max]


def bbox_pixels_to_normalized(bbox: list[int], *, width: int, height: int) -> list[float]:
    x_min, y_min, x_max, y_max = validate_bbox_pixels(bbox, width=width, height=height)
    return [x_min / width, y_min / height, x_max / width, y_max / height]


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


class ManualRegionIn(BaseModel):
    region_type: str
    bbox_normalized: list[float]
    confidence: float | None = None

    @field_validator("region_type")
    @classmethod
    def validate_region_type(cls, value: str) -> str:
        if value not in REGION_TYPES - {"whole_page"}:
            raise ValueError("unsupported region type")
        return value

    @field_validator("bbox_normalized")
    @classmethod
    def validate_bbox(cls, value: list[float]) -> list[float]:
        return validate_bbox_normalized(value)


class ManualRegionsIn(BaseModel):
    regions: list[ManualRegionIn] = Field(min_length=1)


class DrawingTaskOut(BaseModel):
    task_id: uuid.UUID
    revision_id: uuid.UUID | None = None
    status: str


class DrawingLayoutStatusOut(BaseModel):
    task_id: uuid.UUID
    status: str
    error_code: str | None = None
    error_message: str | None = None


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


class DrawingRegionListOut(BaseModel):
    items: list[DrawingRegionOut]
    total: int


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

    def original_to_inference_bbox(self, bbox: list[int]) -> list[int]:
        x_min, y_min, x_max, y_max = validate_bbox_pixels(bbox, width=self.original_width, height=self.original_height)
        return [
            round(x_min * self.scale_original_to_inference_x),
            round(y_min * self.scale_original_to_inference_y),
            round(x_max * self.scale_original_to_inference_x),
            round(y_max * self.scale_original_to_inference_y),
        ]

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


class DrawingCropPackage(BaseModel):
    schema_version: Literal["drawing_crop_v1"] = "drawing_crop_v1"
    task_id: uuid.UUID
    source_id: uuid.UUID
    original_image: dict
    inference_image: dict
    layout: dict
    regions: list[dict]
    warnings: list[str] = Field(default_factory=list)
