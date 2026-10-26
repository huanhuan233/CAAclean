# 图纸事实提取的坐标映射与比较符解析工具；保留无法转成数字的文本。
from __future__ import annotations

from dataclasses import dataclass


# 同时保存原图像素框和相对于原图宽高的归一化框。
@dataclass
class BboxMapping:
    bbox_pixels: list[int]
    bbox_normalized: list[float]


# 将裁剪图归一化框映射回原图；符合启发式条件的大坐标直接视作原图像素。
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
    # 大于 1 且未超过原图边界的坐标被当作原图像素；这里不会再加裁剪偏移。
    if max(x_min, y_min, x_max, y_max) > 1 and x_max <= original_width and y_max <= original_height:
        pixels = [round(x_min), round(y_min), round(x_max), round(y_max)]
        return BboxMapping(
            bbox_pixels=pixels,
            bbox_normalized=[pixels[0] / original_width, pixels[1] / original_height, pixels[2] / original_width, pixels[3] / original_height],
        )
    # 其余坐标按裁剪图的 0～1 比例解释，乘裁剪尺寸后叠加扩边框左上角。
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


# 识别大于等于、小于等于和近似前缀；仅对去除前缀后的纯数字做浮点转换。
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
    # 带单位文本、范围或复合表达式不会被拆解，转数字失败后仍保留原文。
    try:
        normalized = float(cleaned)
        value_type = "number"
    except ValueError:
        normalized = text
        value_type = "string"
        operator = "categorical" if operator == "eq" else operator
    return operator, normalized, value_type
