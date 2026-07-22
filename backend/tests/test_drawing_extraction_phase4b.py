from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.drawing.extraction_client import VisionModelError, parse_model_json
from app.drawing.extraction_repository import MemoryExtractionRepository
from app.drawing.extraction_schemas import (
    DrawingFact,
    ProductInfoResult,
    TableRow,
    TableExtractionResult,
    TargetRowResult,
)
from app.drawing.extraction_service import DrawingExtractionService
from app.drawing.extraction_utils import local_bbox_to_original
from app.drawing.router import get_drawing_service
from app.main import app


def product_payload():
    return {
        "component_code": "XMS06",
        "component_name_raw": None,
        "component_type_raw": "带颈对焊",
        "subtype_raw": "WN",
        "facing_type": "RF",
        "material": "SUS316",
        "pressure_class": "PN16",
        "standard_number": "HG/T 20592-2009",
        "standard_title": None,
        "series": "B",
        "other_metadata": {},
    }


def table_payload():
    return {
        "title": "选型表",
        "headers": ["公称尺寸", "A1", "D", "K", "L", "n", "适用螺栓", "C", "N", "S", "H1", "R", "H", "d", "f1"],
        "header_hierarchy": [],
        "merged_cells": [],
        "rows": [
            {
                "row_identifier": {"code": "XMS06", "dn": "DN80"},
                "cells": {
                    "A1": "89",
                    "D": "200",
                    "K": "160",
                    "L": "18",
                    "n": "8",
                    "适用螺栓": "M16",
                    "C": "20",
                    "N": "105",
                    "S": "≥3.2",
                    "H1": "≈10",
                    "R": "6",
                    "H": "50",
                    "d": "138",
                    "f1": "2",
                },
                "bbox_local": [0.0, 0.68, 1.0, 0.76],
            }
        ],
        "row_identifiers": [{"code": "XMS06", "dn": "DN80"}],
        "units": {"default": "mm"},
        "operator_information": {"S": "gte", "H1": "approx"},
    }


def symbol_payload():
    return {
        "symbols": [
            {"symbol": "D", "visible_label": "D", "visible_geometry_role": "visible dimension label", "annotation_text": "D", "source_bbox_local": [0.1, 0.8, 0.2, 0.9], "confidence": 0.9}
        ]
    }


def target_payload():
    return {
        "requested_code": "XMS06",
        "requested_dn": 80,
        "matched_code": "XMS06",
        "matched_dn": 80,
        "selected_row": table_payload()["rows"][0],
        "row_bbox_local": [0.0, 0.68, 1.0, 0.76],
        "selection_confidence": 0.97,
        "warnings": [],
        "inferred_from_filename": False,
        "needs_review": False,
    }


def test_target_row_result_accepts_common_vlm_type_drift():
    payload = target_payload()
    payload["warnings"] = "The requested code XMS06 is present in the dimensional table."
    payload["inferred_from_filename"] = None
    payload["needs_review"] = None

    result = TargetRowResult.model_validate(payload)

    assert result.warnings == ["The requested code XMS06 is present in the dimensional table."]
    assert result.inferred_from_filename is False
    assert result.needs_review is False


def table_payload_with_multiple_rows():
    payload = table_payload()
    payload["rows"].append(
        {
            "row_identifier": {"code": "XMS06", "dn": "DN200"},
            "cells": {
                "A1": "219",
                "D": "340",
                "K": "295",
                "L": "22",
                "n": "12",
                "适用螺栓": "M20",
                "C": "24",
                "N": "268",
                "S": ">=6.3",
                "H1": "~12",
                "R": "8",
                "H": "60",
                "d": "273",
                "f1": "2",
            },
            "bbox_local": [0.0, 0.78, 1.0, 0.86],
        }
    )
    payload["row_identifiers"].append({"code": "XMS06", "dn": "DN200"})
    return payload


def table_payload_with_list_rows():
    return {
        "title": "参数表",
        "headers": ["型号", "钢管外径", "法兰外径", "连接尺寸", "C", "N", "S≥", "H1≈", "R", "H", "d", "f1"],
        "header_hierarchy": [
            ["型号", "钢管外径", "法兰外径", "连接尺寸", "C", "N", "S≥", "H1≈", "R", "H", "d", "f1"],
            ["代码", "公称尺寸", "A1", "D", "K", "L", "n", "适用螺栓", "C", "N", "S≥", "H1≈", "R", "H", "d", "f1"],
        ],
        "merged_cells": [],
        "rows": [
            {
                "row_identifier": "DN80",
                "cells": ["DN80", "89", "200", "160", "18", "8", "M16", "20", "105", "3.2", "10", "6", "50", "138", "2"],
                "bbox_local": [0.0, 0.68, 1.0, 0.76],
            }
        ],
        "row_identifiers": ["DN80"],
        "units": {"default": "mm"},
        "operator_information": {"S": "gte", "H1": "approx"},
    }


class FakeVisionClient:
    def __init__(self, payloads=None, *, errors=None):
        self.payloads = list(payloads or [product_payload(), table_payload(), symbol_payload()])
        self.errors = list(errors or [])
        self.calls = []
        self.health_checked = False

    async def health_check(self):
        self.health_checked = True

    async def complete_json(self, *, task_name, schema, messages, image_paths):
        self.calls.append({"task_name": task_name, "image_paths": image_paths, "messages": messages})
        if self.errors:
            error = self.errors.pop(0)
            if error:
                raise error
        return self.payloads.pop(0)


def make_package(tmp_path):
    whole = tmp_path / "whole_inference.png"
    crop = tmp_path / "crop.png"
    whole.write_bytes(b"whole")
    crop.write_bytes(b"crop")
    task_id = uuid4()
    source_id = uuid4()
    product_region_id = uuid4()
    diagram_region_id = uuid4()
    table_region_id = uuid4()
    return {
        "schema_version": "drawing_crop_v1",
        "task_id": str(task_id),
        "source_id": str(source_id),
        "original_image": {"width": 1000, "height": 800, "sha256": "orig"},
        "inference_image": {"width": 500, "height": 400, "sha256": "inf", "file_path": str(whole)},
        "layout": {"provider": "manual", "status": "completed"},
        "regions": [
            {"id": str(product_region_id), "region_type": "product_information", "padded_bbox_pixels": [0, 0, 500, 100], "crop_width": 500, "crop_height": 100, "crop_file_path": str(crop), "provider": "manual"},
            {"id": str(diagram_region_id), "region_type": "dimension_diagram", "padded_bbox_pixels": [100, 100, 900, 500], "crop_width": 800, "crop_height": 400, "crop_file_path": str(crop), "provider": "manual"},
            {"id": str(table_region_id), "region_type": "parameter_table", "padded_bbox_pixels": [0, 500, 1000, 800], "crop_width": 1000, "crop_height": 300, "crop_file_path": str(crop), "provider": "manual"},
        ],
        "warnings": [],
    }


def test_parse_model_json_accepts_markdown_wrapped_json():
    payload = parse_model_json("```json\n{\"component_code\":\"XMS06\"}\n```")

    assert payload == {"component_code": "XMS06"}


def test_parse_model_json_rejects_non_json():
    with pytest.raises(VisionModelError) as exc:
        parse_model_json("not json")

    assert exc.value.code == "vision_invalid_json"


def test_pydantic_rejects_missing_required_and_wrong_number_type():
    with pytest.raises(Exception):
        DrawingFact(
            fact_key="dimension.D",
            fact_type="dimension",
            operator="eq",
            raw_value="200",
            normalized_value="abc",
            value_type="number",
            source_region_id=uuid4(),
            confidence=0.9,
        )


def test_bbox_local_to_original_mapping_and_precision_flags():
    mapped = local_bbox_to_original([0.1, 0.2, 0.3, 0.4], padded_bbox_pixels=[100, 200, 500, 600], crop_width=400, crop_height=400, original_width=1000, original_height=800)

    assert mapped.bbox_pixels == [140, 280, 220, 360]
    assert mapped.bbox_normalized == [0.14, 0.35, 0.22, 0.45]


@pytest.mark.asyncio
async def test_extraction_builds_facts_with_operators_and_no_flange_fields(tmp_path):
    repo = MemoryExtractionRepository()
    client = FakeVisionClient()
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package

    result = await service.extract(package["task_id"], target_code="XMS06", target_dn=80, force=False)

    assert client.health_checked is True
    facts = {fact.fact_key: fact for fact in result.facts}
    assert facts["product.pressure_class"].normalized_value == "PN16"
    assert facts["dimension.S"].operator == "gte"
    assert facts["dimension.H1"].operator == "approx"
    assert facts["dimension.D"].normalized_value == 200.0
    assert all("flange_" not in fact.fact_key for fact in result.facts)
    assert result.target_row.selected_row == {}
    assert all(call["image_paths"] for call in client.calls)
    assert len(repo.current_facts[package["task_id"]]) == len(result.facts)


@pytest.mark.asyncio
async def test_extraction_reads_whole_table_without_target_row_model_call(tmp_path):
    repo = MemoryExtractionRepository()
    client = FakeVisionClient(payloads=[product_payload(), table_payload_with_multiple_rows(), symbol_payload()])
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package

    result = await service.extract(package["task_id"], target_code="XMS06", target_dn=200, force=False)

    assert [call["task_name"] for call in client.calls] == ["product_information", "parameter_table", "symbol_definitions"]
    assert result.target_row.selected_row == {}
    assert {fact.metadata.get("row_dn") for fact in result.facts if fact.fact_type == "dimension"} == {80, 200}


@pytest.mark.asyncio
async def test_facts_query_filters_already_extracted_rows_without_model_call(tmp_path):
    repo = MemoryExtractionRepository()
    client = FakeVisionClient(payloads=[product_payload(), table_payload_with_multiple_rows(), symbol_payload()])
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package
    await service.extract(package["task_id"], target_code=None, target_dn=None, force=False)

    rows, total = await repo.list_facts(package["task_id"], target_code="XMS06", target_dn=200, page=1, page_size=100)

    assert total > 0
    dimension_facts = {fact.symbol: fact for fact in rows if fact.fact_type == "dimension"}
    assert dimension_facts["D"].normalized_value == 340.0
    assert all(fact.metadata.get("row_dn") == 200 for fact in rows if fact.fact_type == "dimension")
    assert [call["task_name"] for call in client.calls] == ["product_information", "parameter_table", "symbol_definitions"]


@pytest.mark.asyncio
async def test_facts_query_does_not_drop_dn_match_when_table_row_omits_merged_code(tmp_path):
    repo = MemoryExtractionRepository()
    table = table_payload_with_multiple_rows()
    table["rows"][0]["row_identifier"].pop("code")
    client = FakeVisionClient(payloads=[product_payload(), table, symbol_payload()])
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package
    await service.extract(package["task_id"], target_code=None, target_dn=None, force=False)

    rows, total = await repo.list_facts(package["task_id"], target_code="XMS06", target_dn=80, page=1, page_size=100)

    assert total > 0
    dimension_facts = {fact.symbol: fact for fact in rows if fact.fact_type == "dimension"}
    assert dimension_facts["D"].normalized_value == 200.0


@pytest.mark.asyncio
async def test_list_cells_are_expanded_with_table_headers_into_dimension_facts(tmp_path):
    repo = MemoryExtractionRepository()
    client = FakeVisionClient(payloads=[product_payload(), table_payload_with_list_rows(), symbol_payload()])
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package

    result = await service.extract(package["task_id"], target_code=None, target_dn=None, force=False)

    facts = {fact.symbol: fact for fact in result.facts if fact.fact_type == "dimension"}
    assert facts["D"].normalized_value == 200.0
    assert facts["K"].normalized_value == 160.0
    assert facts["L"].normalized_value == 18.0
    assert facts["n"].normalized_value == 8.0
    assert facts["S"].operator == "gte"
    assert facts["H1"].operator == "approx"
    assert facts["D"].metadata["row_dn"] == 80


@pytest.mark.asyncio
async def test_region_level_evidence_marks_needs_review(tmp_path):
    repo = MemoryExtractionRepository()
    table = table_payload()
    table["rows"][0].pop("bbox_local")
    client = FakeVisionClient(payloads=[product_payload(), table, symbol_payload()])
    service = DrawingExtractionService(repo, vision_client=client)
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package

    result = await service.extract(package["task_id"], target_code="XMS06", target_dn=80, force=False)

    assert result.facts[0].source_bbox_precision in {"region", "row", "cell"}
    assert any(fact.source_bbox_precision == "region" and fact.needs_review for fact in result.facts)


@pytest.mark.asyncio
async def test_reextract_replaces_current_facts_without_duplicates(tmp_path):
    repo = MemoryExtractionRepository()
    package = make_package(tmp_path)
    repo.crop_packages[package["task_id"]] = package
    service = DrawingExtractionService(repo, vision_client=FakeVisionClient())

    first = await service.extract(package["task_id"], target_code="XMS06", target_dn=80, force=False)
    service.vision_client = FakeVisionClient()
    second = await service.extract(package["task_id"], target_code="XMS06", target_dn=80, force=True)

    assert len(repo.current_facts[package["task_id"]]) == len(second.facts)
    assert len(first.facts) == len(second.facts)
    assert repo.generation_no[package["task_id"]] == 2


@pytest.mark.asyncio
async def test_vision_errors_are_mapped():
    service = DrawingExtractionService(MemoryExtractionRepository(), vision_client=FakeVisionClient(errors=[VisionModelError("vision_model_not_multimodal", "bad")]))

    with pytest.raises(VisionModelError) as exc:
        await service.vision_client.complete_json(task_name="x", schema=dict, messages=[], image_paths=[Path("x")])

    assert exc.value.code == "vision_model_not_multimodal"


def test_api_extract_status_result_and_facts_do_not_call_model_on_get():
    task_id = uuid4()
    calls = {"extract": 0}

    async def get_task(_task_id):
        return SimpleNamespace(id=task_id)

    class FakeService:
        repository = SimpleNamespace(get_task=get_task)

        async def extract_drawing_facts(self, task_id, target_code=None, target_dn=None, force=False):
            calls["extract"] += 1
            return {"task_id": str(task_id), "status": "review_ready"}

        async def get_extraction_status(self, task_id):
            return {"task_id": str(task_id), "status": "review_ready", "error_code": None, "error_message": None}

        async def get_extraction_result(self, task_id):
            return {"task_id": str(task_id), "facts": []}

        async def list_drawing_facts(self, task_id, **params):
            return {"items": [], "total": 0, "page": params["page"], "page_size": params["page_size"]}

        async def retry_extraction(self, task_id):
            calls["extract"] += 1
            return {"task_id": str(task_id), "status": "review_ready"}

    app.dependency_overrides[get_drawing_service] = lambda: FakeService()
    client = TestClient(app)

    assert client.post(f"/api/cad/spec/tasks/{task_id}/extract", json={"target_code": "XMS06", "target_dn": 80}).status_code == 202
    assert client.get(f"/api/cad/spec/tasks/{task_id}/extraction/status").status_code == 200
    assert client.get(f"/api/cad/spec/tasks/{task_id}/extraction").status_code == 200
    assert client.get(f"/api/cad/spec/tasks/{task_id}/facts", params={"symbol": "D"}).status_code == 200

    app.dependency_overrides.pop(get_drawing_service, None)
    assert calls["extract"] == 0
