from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pydantic import ValidationError

from app.drawing.extraction_client import VisionModelError
from app.patent_annotation.image_utils import prepare_patent_images
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.schemas import (
    LocalizationCandidate,
    ModelLocalizationBox,
    ModelLocalizationItem,
    ModelLocalizationOutput,
    NormalizedBox,
    NormalizedLocalizationItem,
    NormalizedLocalizationResult,
    NormalizedPoint,
)


PATENT_LOCALIZATION_SYSTEM_PROMPT = r"""
你是一个专门处理机械专利附图的视觉定位模型。

你的任务不是解释专利，也不是绘制引线，而是：

针对候选对象列表中的每一个编号，
判断它是否在当前无标注机械附图中真实可见，
并返回一个适合作为专利引线终点的精确坐标 anchor，
以及该对象当前可见部分的紧致边界框 bbox。

你会收到两张内容完全相同的图片：

- IMAGE_1：干净的黑白机械线稿，用于识别零件和结构；
- IMAGE_2：同一张线稿叠加了 0～1000 坐标网格，仅用于读取坐标。

识别物体时以 IMAGE_1 为准；
确定坐标时参考 IMAGE_2；
不得把坐标网格、页面边框或网格数字当成机械结构。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、视觉证据优先
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

专利文本只用于帮助你理解：

- 部件名称；
- 部件之间的连接、包含、左右和内外关系；
- 当前附图的视图类型；
- 当前图预计需要检查的编号。

文本不能代替图像证据。

即使正文说某个部件存在，
如果当前图中没有可指认的可见轮廓，
也必须返回 visible=false。

只有当你能够在图中指出明确的线条、轮廓、孔槽、齿形、
弹簧线圈、轴体或其他独特结构时，才能返回 visible=true。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、可见性的定义
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下情况可以判定 visible=true：

1. 部件整体可见；
2. 部件只露出一部分，但露出的线条足以确定它；
3. 剖视图或剖开视图中，内部部件因外壳被剖开而可见；
4. 局部放大图中出现了该部件的局部结构；
5. 同一编号有多个实例，至少有一个实例清晰可见。

以下情况必须判定 visible=false：

1. 部件被其他结构完全遮挡；
2. 只能从文字推断它存在，但图上没有可见证据；
3. 当前图展示的是其他视角或其他局部；
4. 只能看到与它连接的部件，不能看到它本身；
5. 无法区分它与相邻部件；
6. 只能猜测位置。

注意：

- “位于内部”不等于不可见；
- 剖视图中实际暴露出的内部部件仍然属于可见；
- 线条交叉不一定表示两个零件连接；
- 不得仅凭物体中心位置猜测部件。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、anchor 的定义
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

anchor 是最终专利引线的终点，不是物体中心点。

anchor 必须满足：

1. 位于该部件真实可见的轮廓线或结构线上；
2. 位于 bbox 内部或边界上；
3. 尽量选择具有辨识度的特征位置；
4. 尽量选择周围较空、适合引线接入的位置；
5. 避免选择多个部件共用或重叠的边界；
6. 避免落在大片空白处；
7. 避免所有相邻部件返回完全相同的坐标。

不同结构的 anchor 选择原则：

- 轴、杆、丝杆：
  选择轴体侧边轮廓线，不要选择轴体中间的空白区域。

- 圆柱、套筒、壳体：
  选择清楚的外轮廓线，优先选择不与其他零件重合的位置。

- 孔、槽口、开口：
  选择孔或槽的边界线，不要只返回孔中心的空白位置。

- 齿轮：
  选择齿形轮廓或能明确证明齿轮存在的边界。

- 齿套、旋钮：
  选择其独立的外侧齿形、凸纹或圆柱轮廓，
  不要指向内部被包围的其他齿轮。

- 弹簧：
  选择中部清晰可见的一段线圈，不要选择弹簧旁边的空白。

- 薄板、扣动板、支架：
  选择其独立外边缘，不要选择与母体共用的线。

- 大型主体零件：
  不要返回整个装配体中心；
  应选择该主体自身独特且清晰的外轮廓。

如果同一编号有多个可见实例：

- 选择轮廓最完整、最清晰、最容易标注的一个实例；
- 不要取多个实例坐标的平均值；
- 每个编号只返回一个代表性 anchor。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、bbox 的定义
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

bbox 表示该部件在当前图中可见部分的紧致边界框。

要求：

1. 使用整张图的 0～1000 坐标；
2. 尽量紧密包围目标可见部分；
3. 不要把整个装配体作为一个小零件的 bbox；
4. 不要包含大面积无关零件；
5. 允许部分遮挡部件只框住当前可见部分；
6. 必须满足：
   x_min < x_max
   y_min < y_max
7. anchor 必须位于 bbox 内部或边界上。

visible=true 时，原则上必须同时返回 anchor 和 bbox。

visible=false 时：

- anchor 必须为 null；
- bbox 必须为 null。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、局部放大标记
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

当候选 kind=detail_marker，例如 A：

- 在父图中：
  bbox 应框住需要被放大的局部区域，
  anchor 位于该区域中心或清晰边界附近。

- 在局部放大图中：
  如果图中存在表示放大视图范围的外部圆形或边界，
  anchor 可以落在该边界上；
  bbox 应覆盖该局部放大视图的主要区域。

不得把普通圆孔误认为局部放大标记。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
六、必须忽略的内容
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

不得将以下内容识别为部件：

- 页面边框；
- PDF 裁切边界；
- 坐标网格；
- 网格数字；
- 页码；
- “说明书附图”等标题；
- 图号文字；
- 空白区域；
- 非候选对象；
- 为方便显示而添加的外框；
- 与候选无关的装饰圆。

detail_marker 除外。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
七、置信度标准
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

confidence 必须反映真实不确定性：

0.90～1.00：
目标唯一、轮廓清楚、与文本关系完全一致。

0.75～0.89：
目标较清楚，但存在少量遮挡、线条密集或相邻结构干扰。

0.55～0.74：
有合理视觉证据，但边界或具体实例存在歧义，应人工审核。

低于 0.55：
无法可靠确定。通常应返回 visible=false。

不得为了凑齐结果而虚高置信度。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
八、输出规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 必须为候选列表中的每一项返回一个结果；
2. 返回顺序必须与候选列表顺序一致；
3. 不得新增候选列表之外的编号；
4. 不得修改 ref_no；
5. name 应与候选名称一致；
6. 每个 ref_no 最多返回一项；
7. 坐标均为整数，范围 0～1000；
8. reason 使用简短中文，说明依据的可见特征；
9. 不输出分析过程；
10. 不输出 Markdown；
11. 不输出 JSON 之外的任何内容。

严格输出：

{
  "items": [
    {
      "ref_no": "字符串",
      "name": "字符串",
      "visible": true,
      "anchor": {
        "x": 0到1000的整数,
        "y": 0到1000的整数
      },
      "bbox": {
        "x_min": 0到1000的整数,
        "y_min": 0到1000的整数,
        "x_max": 0到1000的整数,
        "y_max": 0到1000的整数
      },
      "confidence": 0到1之间的小数,
      "reason": "简短的视觉依据"
    }
  ],
  "warnings": []
}

请在内部依次完成：

1. 判断当前图属于整体图、剖视图、局部图还是放大图；
2. 理解装配体的主要轴向和结构层次；
3. 对每个候选寻找唯一视觉证据；
4. 先确定大致网格区域；
5. 再将 anchor 精确放到最近的目标轮廓线上；
6. 最后检查 anchor、bbox、visible 和 confidence 是否相互一致。

最终只输出 JSON。
"""
DOCUMENT_CONTEXT_LIMIT = 24_000


class PatentLocalizationService:
    def __init__(self, vision_client, model_name: str | None = None):
        self.vision_client = vision_client
        self.model_name = model_name or getattr(vision_client, "model", "")

    async def localize(
        self,
        image_path: Path,
        *,
        figure_no: str,
        figure_description: str,
        figure_context: str,
        candidates: list[LocalizationCandidate],
        work_dir: Path,
        document_context: str = "",
    ) -> NormalizedLocalizationResult:
        assets = prepare_patent_images(image_path, work_dir)
        merged: dict[str, NormalizedLocalizationItem] = {}
        item_order: list[str] = []
        warnings: list[str] = []
        known_by_ref = {candidate.ref_no: candidate for candidate in candidates}
        prompt = build_patent_localization_prompt(
            figure_no=figure_no,
            figure_description=figure_description,
            figure_context=figure_context,
            document_context=document_context,
            candidates=candidates,
            model_name=self.model_name,
        )
        try:
            payload = await self.vision_client.complete_json(
                task_name="patent_page_localization",
                schema=ModelLocalizationOutput,
                messages=[{"type": "text", "text": prompt}],
                image_paths=[assets.clean_path, assets.grid_path],
                system_prompt=PATENT_LOCALIZATION_SYSTEM_PROMPT,
            )
        except VisionModelError as exc:
            raise PatentAnnotationError("patent_localization_failed", exc.message) from exc

        for item in _valid_model_items(payload, warnings):
            ref_no = item.ref_no.strip()
            if not _valid_ref_no(ref_no):
                warnings.append(f"invalid_ref_{ref_no or 'empty'}")
                continue
            candidate = known_by_ref.get(ref_no)
            if candidate is None and (
                not document_context or not _context_contains_ref(document_context, ref_no)
            ):
                warnings.append(f"unknown_ref_{ref_no}")
                continue
            normalized, item_warnings = _normalize_item(
                item.model_copy(update={"ref_no": ref_no}),
                candidate,
            )
            warnings.extend(item_warnings)
            previous = merged.get(ref_no)
            if previous is None:
                item_order.append(ref_no)
            if previous is None or normalized.confidence > previous.confidence:
                merged[ref_no] = normalized

        ordered = [merged[ref_no] for ref_no in item_order]
        return NormalizedLocalizationResult(items=ordered, warnings=_dedupe(warnings))


def build_patent_localization_prompt(
    *,
    figure_no: str,
    figure_description: str,
    figure_context: str,
    document_context: str,
    candidates: list[LocalizationCandidate],
    model_name: str | None = None,
) -> str:
    candidate_payload = [{"ref_no": candidate.ref_no, "name": candidate.name} for candidate in candidates]
    context = figure_context[:2000]
    patent_context = document_context[:DOCUMENT_CONTEXT_LIMIT]
    return "\n".join(
        [
            f"Model: {model_name or 'vision'}",
            f"Figure number: {figure_no}",
            f"Figure description: {figure_description}",
            f"Figure context: {context}",
            "MinerU patent document context:",
            patent_context,
            "Candidate objects JSON:",
            json.dumps(candidate_payload, ensure_ascii=False, separators=(",", ":")),
            "请结合 MinerU patent document context 和当前图片，为 Candidate objects JSON 中的每一项返回可见性、坐标和依据。",
        ]
    )


def _valid_model_items(payload, warnings: list[str]) -> list[ModelLocalizationItem]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        warnings.append("invalid_model_output")
        return []
    items: list[ModelLocalizationItem] = []
    for index, raw_item in enumerate(raw_items):
        try:
            items.append(ModelLocalizationItem.model_validate(_coerce_model_item(raw_item)))
        except ValidationError:
            ref = raw_item.get("ref_no") if isinstance(raw_item, dict) else index
            warnings.append(f"invalid_model_item_{ref}")
    return items


def _coerce_model_item(raw_item):
    if not isinstance(raw_item, dict):
        return raw_item
    item = dict(raw_item)
    anchor = item.get("anchor") or item.get("point") or item.get("coordinate") or item.get("coordinates")
    bbox = item.get("bbox") or item.get("box") or item.get("bounding_box")
    if isinstance(anchor, dict) and "anchor" in anchor:
        anchor = anchor.get("anchor")
    if anchor is not None:
        item["anchor"] = _coerce_point(anchor)
    if bbox is not None:
        item["bbox"] = _coerce_box(bbox)
    confidence = item.get("confidence")
    if isinstance(confidence, (int, float)) and confidence > 10 and confidence <= 100:
        item["confidence"] = confidence / 100
    return item


def _coerce_point(value):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return {"x": value[0], "y": value[1]}
    return value


def _coerce_box(value):
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return {"x_min": value[0], "y_min": value[1], "x_max": value[2], "y_max": value[3]}
    if isinstance(value, dict):
        aliases = {
            "x1": "x_min",
            "y1": "y_min",
            "x2": "x_max",
            "y2": "y_max",
            "left": "x_min",
            "top": "y_min",
            "right": "x_max",
            "bottom": "y_max",
        }
        return {aliases.get(key, key): val for key, val in value.items()}
    return value


def _normalize_item(
    item: ModelLocalizationItem,
    candidate: LocalizationCandidate | None,
) -> tuple[NormalizedLocalizationItem, list[str]]:
    warnings: list[str] = []
    if _has_non_finite_coordinates(item):
        warnings.append(f"non_finite_coordinate_{item.ref_no}")
    anchor = _normalize_point(item.anchor) if item.anchor else None
    bbox = _normalize_box(item.bbox) if item.bbox else None
    visible = item.visible

    if visible and anchor is None:
        visible = False
        warnings.append(f"visible_without_anchor_{item.ref_no}")

    review_state = _review_state(visible, item.confidence)
    if visible and anchor and bbox and not _point_inside_bbox(anchor, bbox):
        if review_state != "rejected":
            review_state = "review"
        warnings.append(f"anchor_outside_bbox_{item.ref_no}")
    model_name = item.name.strip()[:120] if item.name and item.name.strip() else None
    if candidate and model_name and not _names_match(model_name, candidate.name):
        if review_state == "accepted":
            review_state = "review"
        warnings.append(f"name_mismatch_{item.ref_no}")
    if candidate is None and not model_name:
        if review_state == "accepted":
            review_state = "review"
        warnings.append(f"missing_name_{item.ref_no}")

    return (
        NormalizedLocalizationItem(
            ref_no=item.ref_no,
            name=model_name,
            visible=visible,
            confidence=item.confidence,
            reason=item.reason[:120],
            anchor=anchor if visible else None,
            bbox=bbox if visible else None,
            review_state=review_state,
        ),
        warnings,
    )


def _review_state(visible: bool, confidence: float) -> str:
    if not visible or confidence < 0.45:
        return "rejected"
    if confidence >= 0.72:
        return "accepted"
    return "review"


def _names_match(model_name: str, candidate_name: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", value).casefold()

    model_value = normalize(model_name)
    candidate_value = normalize(candidate_name)
    return bool(
        model_value
        and candidate_value
        and (
            model_value == candidate_value
            or model_value in candidate_value
            or candidate_value in model_value
        )
    )


def _valid_ref_no(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]|\d+[A-Za-z]?", value))


def _context_contains_ref(context: str, ref_no: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(ref_no)}(?![A-Za-z0-9])",
            context,
        )
    )


def _normalize_point(point) -> NormalizedPoint:
    scale = _coordinate_scale([point.x, point.y])
    return NormalizedPoint(x=_clamp(point.x / scale), y=_clamp(point.y / scale))


def _normalize_box(box: ModelLocalizationBox | None) -> NormalizedBox | None:
    if box is None:
        return None
    scale = _coordinate_scale([box.x_min, box.y_min, box.x_max, box.y_max])
    x_min, x_max = sorted((_clamp(box.x_min / scale), _clamp(box.x_max / scale)))
    y_min, y_max = sorted((_clamp(box.y_min / scale), _clamp(box.y_max / scale)))
    return NormalizedBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _point_inside_bbox(point: NormalizedPoint, bbox: NormalizedBox) -> bool:
    return bbox.x_min <= point.x <= bbox.x_max and bbox.y_min <= point.y <= bbox.y_max


def _has_non_finite_coordinates(item: ModelLocalizationItem) -> bool:
    values: list[float] = []
    if item.anchor:
        values.extend([item.anchor.x, item.anchor.y])
    if item.bbox:
        values.extend([item.bbox.x_min, item.bbox.y_min, item.bbox.x_max, item.bbox.y_max])
    return any(not math.isfinite(value) for value in values)


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _coordinate_scale(values: list[float]) -> float:
    finite = [abs(value) for value in values if math.isfinite(value)]
    return 1.0 if finite and max(finite) <= 1.0 else 1000.0


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
