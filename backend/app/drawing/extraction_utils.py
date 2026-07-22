from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BboxMapping:
    bbox_pixels: list[int]
    bbox_normalized: list[float]


def local_bbox_to_original(
    bbox_local: list[float],
    *,
    padded_bbox_pixels: list[int],
    crop_width: int,
    crop_height: int,
    original_width: int,
    original_height: int,
) -> BboxMapping:
    x_min, y_min, x_max, y_max = [float(value) for value in bbox_local]
    if max(x_min, y_min, x_max, y_max) > 1 and x_max <= original_width and y_max <= original_height:
        pixels = [round(x_min), round(y_min), round(x_max), round(y_max)]
        return BboxMapping(
            bbox_pixels=pixels,
            bbox_normalized=[pixels[0] / original_width, pixels[1] / original_height, pixels[2] / original_width, pixels[3] / original_height],
        )
    crop_x1, crop_y1, crop_x2, crop_y2 = [int(value) for value in padded_bbox_pixels]
    width = crop_width or crop_x2 - crop_x1
    height = crop_height or crop_y2 - crop_y1
    pixels = [
        round(crop_x1 + x_min * width),
        round(crop_y1 + y_min * height),
        round(crop_x1 + x_max * width),
        round(crop_y1 + y_max * height),
    ]
    pixels = [
        max(0, min(original_width, pixels[0])),
        max(0, min(original_height, pixels[1])),
        max(0, min(original_width, pixels[2])),
        max(0, min(original_height, pixels[3])),
    ]
    return BboxMapping(
        bbox_pixels=pixels,
        bbox_normalized=[pixels[0] / original_width, pixels[1] / original_height, pixels[2] / original_width, pixels[3] / original_height],
    )


def parse_operator_and_value(raw_value):
    if raw_value is None:
        return "unknown", None, None
    text = str(raw_value).strip()
    operator = "eq"
    if text.startswith(("≥", ">=")):
        operator = "gte"
    elif text.startswith(("≤", "<=")):
        operator = "lte"
    elif text.startswith(("≈", "~")):
        operator = "approx"
    cleaned = text.replace("≥", "").replace(">=", "").replace("≤", "").replace("<=", "").replace("≈", "").replace("~", "").strip()
    try:
        normalized = float(cleaned)
        value_type = "number"
    except ValueError:
        normalized = text
        value_type = "string"
        operator = "categorical" if operator == "eq" else operator
    return operator, normalized, value_type
