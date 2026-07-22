from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

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
                            "Read visible product information from the drawing. Output JSON only. "
                            "Do not infer hidden values from industry knowledge. Use English keys: "
                            "component_code, component_name_raw, component_type_raw, subtype_raw, facing_type, "
                            "material, pressure_class, standard_number, standard_title, series, other_metadata."
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
                            "Read the complete visible parameter table. Output JSON only. "
                            "Do not select only one target row. Preserve original strings. "
                            "Use English keys: title, headers, header_hierarchy, merged_cells, rows, "
                            "row_identifiers, units, operator_information. Each row should include "
                            "row_identifier, cells, and bbox_local when visible."
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
                messages=[
                    {
                        "type": "text",
                        "text": "Extract visible dimension symbols and geometry roles only. Output JSON only.",
                    }
                ],
                image_paths=_paths_for(package, "dimension_diagram"),
            )
        )

        await self.repository.set_status(task_id, "validating_result", 100, "validating_result")
        result = DrawingExtractionResult(
            task_id=uuid.UUID(str(package["task_id"])),
            source_id=uuid.UUID(str(package["source_id"])),
            product_info=product,
            table=table,
            symbols=symbols,
            target_row=TargetRowResult(),
            facts=_build_facts(package, product, table),
            model_name=getattr(self.vision_client, "model", "fake-vision"),
            prompt_version=PROMPT_VERSION,
            warnings=[],
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


def _build_facts(package: dict, product: ProductInfoResult, table: TableExtractionResult) -> list[DrawingFact]:
    facts: list[DrawingFact] = []
    product_region = _region(package, "product_information")
    table_region = _region(package, "parameter_table")
    original_width = package["original_image"]["width"]
    original_height = package["original_image"]["height"]

    for key, value in _product_values(product).items():
        if key not in {"component_code", "component_type_raw", "facing_type", "material", "pressure_class", "standard_number", "series"}:
            continue
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

    rows = _table_rows(table)
    multi_row = len(rows) > 1
    headers = _leaf_headers(table)
    for row_index, row in enumerate(rows):
        cells = _row_cells(row, headers)
        row_bbox = row.get("bbox_local")
        row_code, row_dn = _row_identity(row)
        if row_dn is None:
            row_dn = _parse_dn(cells.get("dn") or cells.get("DN") or cells.get("公称尺寸") or row.get("row_identifier"))
        for symbol, raw in cells.items():
            if _is_identifier_symbol(symbol):
                continue
            symbol_text = str(symbol)
            symbol_text, raw_for_parse = _normalize_symbol_value(symbol_text, raw)
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
                    fact_key=_dimension_fact_key(symbol_text, row_index=row_index, row_code=row_code, row_dn=row_dn, multi_row=multi_row),
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
                    confidence=0.85,
                    needs_review=needs_review,
                    metadata={"row_index": row_index, "row_code": row_code, "row_dn": row_dn},
                )
            )
    return facts


def _product_values(product: ProductInfoResult) -> dict[str, Any]:
    values = product.model_dump()
    extras = product.model_extra or {}
    aliases = {
        "component_code": ["code", "model", "model_code"],
        "component_type_raw": ["component_type", "type"],
        "facing_type": ["facing", "face_type"],
        "material": ["material_raw"],
        "pressure_class": ["pressure", "pressure_rating"],
        "standard_number": ["standard", "standard_no"],
        "series": ["applicable_series"],
    }
    for target, keys in aliases.items():
        if values.get(target) is None:
            for key in keys:
                if extras.get(key) is not None:
                    values[target] = extras[key]
                    break
    material = values.get("material")
    if isinstance(material, list):
        values["material"] = material[0] if material else None
    return values


def _table_rows(table: TableExtractionResult) -> list[dict]:
    rows = []
    for row in table.rows:
        if isinstance(row, dict):
            rows.append(row)
        elif hasattr(row, "model_dump"):
            rows.append(row.model_dump(mode="json"))
    return rows


def _leaf_headers(table: TableExtractionResult) -> list[str]:
    candidates = table.header_hierarchy[-1] if table.header_hierarchy else table.headers
    return [str(item).strip() for item in candidates if str(item).strip()]


def _row_cells(row: dict, headers: list[str]) -> dict:
    raw_cells = row.get("cells")
    if isinstance(raw_cells, dict):
        return raw_cells
    if not isinstance(raw_cells, list):
        return {}
    cell_values = list(raw_cells)
    if len(headers) == len(cell_values):
        return dict(zip(headers, cell_values, strict=False))
    if len(headers) == len(cell_values) + 1:
        return dict(zip(headers[1:], cell_values, strict=False))
    return {str(index): value for index, value in enumerate(cell_values)}


def _row_identity(row: dict) -> tuple[str | None, int | None]:
    row_identifier = row.get("row_identifier") if isinstance(row.get("row_identifier"), dict) else {}
    cells = row.get("cells") if isinstance(row.get("cells"), dict) else {}
    if isinstance(row.get("row_identifier"), str):
        cells = cells | {"dn": row["row_identifier"]}
    code = _first_text(row_identifier, ["code", "component_code", "model", "model_code"]) or _first_text(
        cells, ["code", "component_code", "model", "model_code"]
    )
    dn = _parse_dn(_first_text(row_identifier, ["dn", "DN"]) or _first_text(cells, ["dn", "DN"]))
    return code, dn


def _first_text(values: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = values.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _parse_dn(value) -> int | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace("DN", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return None


def _is_identifier_symbol(symbol) -> bool:
    text = str(symbol).strip().lower()
    return text in {"code", "component_code", "model", "model_code", "dn", "公称尺寸", "代码", "型号"}


def _normalize_symbol_value(symbol: str, raw) -> tuple[str, Any]:
    text = symbol.strip()
    if text.endswith(("≥", ">=")):
        return text.removesuffix("≥").removesuffix(">="), f">={raw}"
    if text.endswith(("≤", "<=")):
        return text.removesuffix("≤").removesuffix("<="), f"<={raw}"
    if text.endswith(("≈", "~")):
        return text.removesuffix("≈").removesuffix("~"), f"~{raw}"
    return text, raw


def _dimension_fact_key(symbol: str, *, row_index: int, row_code: str | None, row_dn: int | None, multi_row: bool) -> str:
    if not multi_row:
        return f"dimension.{symbol}"
    code_part = _key_part(row_code) or f"row{row_index + 1}"
    dn_part = f"DN{row_dn}" if row_dn is not None else f"row{row_index + 1}"
    return f"dimension.{code_part}.{dn_part}.{symbol}"


def _key_part(value: str | None) -> str | None:
    if not value:
        return None
    return "".join(ch for ch in str(value).strip() if ch.isalnum() or ch in {"_", "-"})
