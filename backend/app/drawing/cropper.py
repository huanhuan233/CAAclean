from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.drawing.layout import LayoutRegion
from app.drawing.preprocessing import sha256_file
from app.drawing.schemas import DrawingError, validate_bbox_pixels


PADDING_BY_REGION_TYPE = {
    "product_information": 0.03,
    "dimension_diagram": 0.05,
    "parameter_table": 0.02,
}


@dataclass
class CropResult:
    region: LayoutRegion
    padded_bbox_pixels: list[int]
    crop_file_path: Path
    crop_file_name: str
    crop_sha256: str
    crop_width: int
    crop_height: int
    mime_type: str = "image/png"


def crop_regions(
    image_path: Path,
    regions: list[LayoutRegion],
    output_dir: Path,
    task_id: uuid.UUID,
    *,
    padding_by_region_type: dict[str, float] | None = None,
) -> list[CropResult]:
    padding = padding_by_region_type or PADDING_BY_REGION_TYPE
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            width, height = image.size
            results = []
            counters: dict[str, int] = {}
            for region in regions:
                validate_bbox_pixels(region.bbox_pixels, width=width, height=height)
                counters[region.region_type] = counters.get(region.region_type, 0) + 1
                padded = region.padded_bbox(width=width, height=height, padding_ratio=padding.get(region.region_type, 0.03))
                cropped = image.crop(tuple(padded))
                file_name = f"{region.region_type}-{counters[region.region_type]}.png"
                if region.region_type == "whole_page":
                    file_name = "whole_inference.png"
                crop_path = output_dir / str(task_id) / file_name
                crop_path.parent.mkdir(parents=True, exist_ok=True)
                cropped.save(crop_path, format="PNG")
                crop_width, crop_height = cropped.size
                results.append(
                    CropResult(
                        region=region,
                        padded_bbox_pixels=padded,
                        crop_file_path=crop_path,
                        crop_file_name=file_name,
                        crop_sha256=sha256_file(crop_path),
                        crop_width=crop_width,
                        crop_height=crop_height,
                    )
                )
        return results
    except DrawingError:
        raise
    except OSError as exc:
        raise DrawingError("crop_failed", "failed to crop drawing regions") from exc
