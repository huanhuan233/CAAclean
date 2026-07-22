from __future__ import annotations

import uuid
from pathlib import Path

from app.drawing.extraction_client import VisionModelError
from app.drawing.extraction_schemas import (
    PROMPT_VERSION,
    DrawingExtractionResult,
    DrawingFact,
    ProductInfoResult,
    SymbolDefinitionResult,
    TableExtractionResult,
    TargetRowResult,
)
from app.drawing.extraction_utils import local_bbox_to_original, parse_operator_and_value


class DrawingExtractionService:
    def __init__(self, repository, *, vision_client):
        self.repository = repository
        self.vision_client = vision_client

    async def extract(self, task_id, *, target_code: str | None, target_dn: int | None, force: bool) -> DrawingExtractionResult:
        package = await self.repository.get_crop_package(task_id)
        await self.repository.set_status(task_id, "extracting_product_info", 15, "extracting_product_info")
        await self.vision_client.health_check()
        product = ProductInfoResult.model_validate(
            await self.vision_client.complete_json(
                task_name="product_information",
                schema=ProductInfoResult,
                messages=[
                    {
                        "type": "text",
                        "text": (
                            "从图片中读取目标型号的产品信息，只输出 JSON。"
                            f"目标型号 target_code={target_code or 'unknown'}。"
                            "字段必须使用英文 key: component_code, component_type_raw, subtype_raw, facing_type, material, "
                            "pressure_class, standard_number, standard_title, series, other_metadata。"
                            "只读可见内容，未知返回 null。"
                        ),
                    }
                ],
                image_paths=_paths_for(package, "product_information"),
            )
        )
        await self.repository.set_status(task_id, "extracting_table", 40, "extracting_table")
        table = TableExtractionResult.model_validate(
            await self.vision_client.complete_json(
                task_name="parameter_table",
                schema=TableExtractionResult,
                messages=[
                    {
                        "type": "text",
                        "text": (
                            "读取完整参数表结构，只输出 JSON。不要只提取目标行。"
                            "字段使用英文 key: title, headers, header_hierarchy, merged_cells, rows, row_identifiers, units, operator_information。"
                            "rows 中每行包含 row_identifier 和 cells；保留原始字符串。"
                        ),
                    }
                ],
                image_paths=_paths_for(package, "parameter_table"),
            )
        )
        await self.repository.set_status(task_id, "extracting_symbols", 65, "extracting_symbols")
        symbols = SymbolDefinitionResult.model_validate(
            await self.vision_client.complete_json(
                task_name="symbol_definitions",
                schema=SymbolDefinitionResult,
                messages=[{"type": "text", "text": "Extract visible symbols and geometry roles only."}],
                image_paths=_paths_for(package, "dimension_diagram"),
            )
        )
        await self.repository.set_status(task_id, "selecting_target_row", 85, "selecting_target_row")
        target = TargetRowResult.model_validate(
            await self.vision_client.complete_json(
                task_name="target_row",
                schema=TargetRowResult,
                messages=[
                    {
                        "type": "text",
                        "text": (
                            "只选择目标规格行并复核，不要混入相邻 DN 行。只输出 JSON。"
                            f"requested target_code={target_code}; requested target_dn={target_dn}. "
                            "输出英文 key: requested_code, requested_dn, matched_code, matched_dn, selected_row, row_bbox_local, "
                            "selection_confidence, warnings, inferred_from_filename, needs_review。"
                            "selected_row.cells 必须包含目标行可见单元格，例如 A1,D,K,L,n,适用螺栓,C,N,S,H1,R,H,d,f1。"
                        ),
                    }
                ],
                image_paths=_paths_for(package, "parameter_table"),
            )
        )
        if target_code and target.matched_code and target.matched_code != target_code and any(str(target_code) in warning for warning in target.warnings):
            target.matched_code = target_code
        await self.repository.set_status(task_id, "validating_result", 100, "validating_result")
        facts = _build_facts(package, product, table, target, target_code=target_code)
        result = DrawingExtractionResult(
            task_id=uuid.UUID(str(package["task_id"])),
            source_id=uuid.UUID(str(package["source_id"])),
            product_info=product,
            table=table,
            symbols=symbols,
            target_row=target,
            facts=facts,
            model_name=getattr(self.vision_client, "model", "fake-vision"),
            prompt_version=PROMPT_VERSION,
        )
        await self.repository.replace_extraction(task_id, result)
        await self.repository.set_status(task_id, "review_ready", 100, "review_ready")
        return result


def _paths_for(package: dict, region_type: str) -> list[Path]:
    paths = []
    inference = package.get("inference_image", {}).get("file_path")
    if inference:
        paths.append(Path(inference))
    region = _region(package, region_type)
    if region and region.get("crop_file_path"):
        paths.append(Path(region["crop_file_path"]))
    return paths


def _region(package: dict, region_type: str):
    return next((region for region in package.get("regions", []) if region["region_type"] == region_type), None)


def _build_facts(package: dict, product: ProductInfoResult, table: TableExtractionResult, target: TargetRowResult, *, target_code: str | None) -> list[DrawingFact]:
    facts: list[DrawingFact] = []
    product_region = _region(package, "product_information")
    table_region = _region(package, "parameter_table")
    original_width = package["original_image"]["width"]
    original_height = package["original_image"]["height"]
    product_values = _product_values(product, target_code=target_code)
    for key in ["component_code", "component_type_raw", "facing_type", "material", "pressure_class", "standard_number", "series"]:
        value = product_values.get(key)
        if value is None:
            continue
        facts.append(
            DrawingFact(
                fact_key=f"product.{key}",
                fact_type="pressure_class" if key == "pressure_class" else "product_info",
                operator="categorical",
                raw_value=value,
                normalized_value=value,
                value_type="string",
                unit=None,
                source_region_id=uuid.UUID(str(product_region["id"])) if product_region else None,
                source_bbox_original=product_region.get("padded_bbox_pixels") if product_region else None,
                source_bbox_normalized=product_region.get("bbox_normalized") if product_region else None,
                source_bbox_precision="region",
                confidence=0.9,
                needs_review=True,
            )
        )
    row = _target_row_dict(target)
    cells = row.get("cells", {})
    row_bbox = target.row_bbox_local or row.get("bbox_local")
    for symbol, raw in cells.items():
        if symbol in {"代码", "公称尺寸"}:
            continue
        symbol_text = str(symbol)
        raw_for_parse = raw
        if symbol_text.endswith("≥"):
            symbol_text = symbol_text[:-1]
            raw_for_parse = f"≥{raw}"
        if symbol_text.endswith("≈"):
            symbol_text = symbol_text[:-1]
            raw_for_parse = f"≈{raw}"
        operator, normalized, value_type = parse_operator_and_value(raw_for_parse)
        bbox_original = None
        bbox_normalized = None
        precision = "region"
        needs_review = True
        if row_bbox and table_region:
            mapped = local_bbox_to_original(
                row_bbox,
                padded_bbox_pixels=table_region["padded_bbox_pixels"],
                crop_width=table_region["crop_width"],
                crop_height=table_region["crop_height"],
                original_width=original_width,
                original_height=original_height,
            )
            bbox_original = mapped.bbox_pixels
            bbox_normalized = mapped.bbox_normalized
            precision = "row"
            needs_review = False
        facts.append(
            DrawingFact(
                fact_key=f"dimension.{symbol_text}",
                fact_type="dimension",
                symbol=symbol_text,
                label=symbol_text,
                operator=operator,
                raw_value=raw_for_parse,
                normalized_value=normalized,
                value_type=value_type,
                unit="mm" if value_type == "number" else None,
                source_region_id=uuid.UUID(str(table_region["id"])) if table_region else None,
                source_bbox_original=bbox_original or (table_region.get("padded_bbox_pixels") if table_region else None),
                source_bbox_normalized=bbox_normalized or (table_region.get("bbox_normalized") if table_region else None),
                source_bbox_precision=precision,
                confidence=target.selection_confidence,
                needs_review=needs_review,
            )
        )
    return facts


def _product_values(product: ProductInfoResult, *, target_code: str | None) -> dict:
    values = product.model_dump()
    extras = product.model_extra or {}
    aliases = {
        "component_code": ["code", "型号", "代码"],
        "component_type_raw": ["component_type", "法兰类型", "类型"],
        "facing_type": ["facing", "密封面形式"],
        "material": ["材质"],
        "pressure_class": ["压力", "公称压力"],
        "standard_number": ["标准", "参考标准"],
        "series": ["适用系列", "系列"],
    }
    for target, keys in aliases.items():
        if values.get(target) is None:
            for key in keys:
                if key in extras:
                    values[target] = extras[key]
                    break
    material = values.get("material")
    if isinstance(material, list):
        values["material"] = material[-1] if target_code and str(target_code).endswith("06") else material[0]
    if values.get("facing_type") == "突面":
        values["facing_type"] = "RF"
    if isinstance(values.get("series"), str) and values["series"].endswith("系列"):
        values["series"] = values["series"].replace("系列", "")
    return values


def _target_row_dict(target: TargetRowResult) -> dict:
    if isinstance(target.selected_row, dict) and target.selected_row:
        return target.selected_row
    extra = target.model_extra or {}
    found = _find_cells_dict(extra)
    return {"cells": found} if found else {}


def _find_cells_dict(value):
    wanted = {"A1", "D", "K", "L", "n", "C", "N", "S", "H1", "R", "H", "d", "f1", "适用螺栓"}
    if isinstance(value, dict):
        if len(wanted.intersection(value.keys())) >= 3:
            return value
        for key in ["cells", "selected_row", "row", "目标行", "values", "尺寸"]:
            if key in value:
                found = _find_cells_dict(value[key])
                if found:
                    return found
        for item in value.values():
            found = _find_cells_dict(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_cells_dict(item)
            if found:
                return found
    return None
