from __future__ import annotations

import hashlib
import io
from pathlib import Path
import asyncio
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.drawing.cropper import crop_regions
from app.drawing.layout import LayoutDetectionResult, LayoutRegion, merge_regions
from app.drawing.preprocessing import DrawingImagePreprocessor
from app.drawing.providers import AutoLayoutProvider, ManualLayoutProvider, MineruLayoutProvider, VisionLayoutProvider
from app.drawing.repository import MemoryDrawingRepository
from app.drawing.router import get_drawing_service
from app.drawing.schemas import DrawingError, ManualRegionIn, validate_bbox_pixels
from app.drawing.service import DrawingLayoutService
from app.main import app


def make_image(path: Path, *, fmt: str = "PNG", size=(120, 80), color=(255, 255, 255)) -> Path:
    image = Image.new("RGB", size, color)
    for x in range(10, size[0] - 10):
        image.putpixel((x, 10), (0, 0, 0))
    image.save(path, format=fmt)
    return path


def test_exif_rotation_is_applied(tmp_path):
    path = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (40, 80), "white")
    exif = Image.Exif()
    exif[274] = 6
    image.save(path, format="JPEG", exif=exif)

    result = DrawingImagePreprocessor(max_image_mb=1, inference_max_side=100).preprocess(path, tmp_path)

    assert result.original_width == 80
    assert result.original_height == 40


@pytest.mark.parametrize("fmt, suffix", [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")])
def test_png_jpg_webp_are_accepted(tmp_path, fmt, suffix):
    path = make_image(tmp_path / f"sample{suffix}", fmt=fmt)

    result = DrawingImagePreprocessor(max_image_mb=1, inference_max_side=64).preprocess(path, tmp_path)

    assert result.inference_width <= 64
    assert result.original_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_corrupted_image_is_rejected(tmp_path):
    path = tmp_path / "bad.png"
    path.write_bytes(b"not an image")

    with pytest.raises(DrawingError) as exc:
        DrawingImagePreprocessor(max_image_mb=1).preprocess(path, tmp_path)

    assert exc.value.code == "drawing_decode_failed"


def test_oversized_image_is_rejected(tmp_path):
    path = make_image(tmp_path / "large.png")

    with pytest.raises(DrawingError) as exc:
        DrawingImagePreprocessor(max_image_mb=0).preprocess(path, tmp_path)

    assert exc.value.code == "drawing_too_large"


def test_coordinate_conversion_round_trip_stays_within_two_pixels(tmp_path):
    path = make_image(tmp_path / "sample.png", size=(400, 200))
    result = DrawingImagePreprocessor(max_image_mb=1, inference_max_side=200).preprocess(path, tmp_path)
    bbox = [25, 20, 325, 180]

    inference = result.original_to_inference_bbox(bbox)
    restored = result.inference_to_original_bbox(inference)

    assert max(abs(a - b) for a, b in zip(bbox, restored)) <= 2


def test_padding_is_clamped_to_image_bounds():
    padded = LayoutRegion(
        region_type="dimension_diagram",
        bbox_pixels=[0, 0, 100, 50],
        confidence=0.9,
        provider="vision",
    ).padded_bbox(width=120, height=80, padding_ratio=0.1)

    assert padded == [0, 0, 110, 55]


def test_invalid_bbox_values_are_rejected():
    with pytest.raises(DrawingError) as exc:
        validate_bbox_pixels([10, 10, 5, 20], width=100, height=100)

    assert exc.value.code == "layout_regions_invalid"


def test_adjacent_text_regions_merge_into_business_region():
    regions = [
        LayoutRegion("product_information", [10, 10, 100, 40], 0.8, "mineru", provider_region_type="text"),
        LayoutRegion("product_information", [105, 12, 200, 42], 0.8, "mineru", provider_region_type="text"),
        LayoutRegion("parameter_table", [10, 200, 300, 390], 0.9, "mineru", provider_region_type="table"),
    ]

    merged = merge_regions(regions, image_width=400, image_height=400, gap_ratio=0.02)

    assert [region.region_type for region in merged] == ["product_information", "parameter_table"]
    assert merged[0].bbox_pixels == [10, 10, 200, 42]


@pytest.mark.asyncio
async def test_mineru_provider_accepts_mock_http_result(tmp_path):
    path = make_image(tmp_path / "sample.png")

    async def transport(_path):
        return {
            "provider_version": "mock",
            "regions": [{"type": "table", "bbox": [10, 20, 100, 70], "score": 0.95}],
        }

    result = await MineruLayoutProvider(mode="http", url="http://mock", transport=transport).detect(path)

    assert result.provider == "mineru"
    assert result.regions[0].region_type == "parameter_table"


@pytest.mark.asyncio
async def test_mineru_timeout_raises_drawing_error(tmp_path):
    path = make_image(tmp_path / "sample.png")

    async def transport(_path):
        raise TimeoutError

    with pytest.raises(DrawingError) as exc:
        await MineruLayoutProvider(mode="http", url="http://mock", transport=transport).detect(path)

    assert exc.value.code == "mineru_timeout"


@pytest.mark.asyncio
async def test_mineru_empty_result_is_invalid(tmp_path):
    path = make_image(tmp_path / "sample.png")

    async def transport(_path):
        return {"regions": []}

    with pytest.raises(DrawingError) as exc:
        await MineruLayoutProvider(mode="http", url="http://mock", transport=transport).detect(path)

    assert exc.value.code == "layout_no_regions"


@pytest.mark.asyncio
async def test_auto_falls_back_to_vision_when_mineru_fails(tmp_path):
    path = make_image(tmp_path / "sample.png", size=(300, 240))
    mineru = MineruLayoutProvider(mode="disabled")
    vision = VisionLayoutProvider()

    result = await AutoLayoutProvider(mineru=mineru, vision=vision).detect(path)

    assert result.provider == "vision"
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_auto_enters_needs_manual_when_vision_also_fails(tmp_path):
    path = make_image(tmp_path / "sample.png")

    class FailingVision:
        async def detect(self, image_path):
            raise DrawingError("vision_layout_failed", "failed")

    result = await AutoLayoutProvider(mineru=MineruLayoutProvider(mode="disabled"), vision=FailingVision()).detect(path)

    assert result.status == "needs_manual_layout"


def test_crop_sha256_is_stable(tmp_path):
    path = make_image(tmp_path / "sample.png", size=(100, 80))
    region = LayoutRegion("parameter_table", [10, 10, 60, 50], 0.9, "manual")

    first = crop_regions(path, [region], tmp_path, uuid4())[0]
    second = crop_regions(path, [region], tmp_path, uuid4())[0]

    assert first.crop_sha256 == second.crop_sha256
    assert first.crop_width == 52
    assert first.crop_height == 42


@pytest.mark.asyncio
async def test_manual_regions_recompute_crop_and_replace_active_regions(tmp_path):
    image_path = make_image(tmp_path / "drawing.png", size=(300, 200))
    repo = MemoryDrawingRepository()
    service = DrawingLayoutService(
        repo,
        work_dir=tmp_path / "work",
        provider=ManualLayoutProvider([]),
        max_image_mb=1,
        inference_max_side=200,
    )
    task = await service.create_task(revision_id=uuid4(), drawing_file=image_path, target_code=None, target_dn=None)

    await service.apply_manual_regions(
        task.id,
        [ManualRegionIn(region_type="parameter_table", bbox_normalized=[0.1, 0.1, 0.9, 0.9])],
    )
    first = await service.list_regions(task.id)
    await service.apply_manual_regions(
        task.id,
        [ManualRegionIn(region_type="dimension_diagram", bbox_normalized=[0.2, 0.2, 0.8, 0.8])],
    )
    second = await service.list_regions(task.id)

    assert len(first) == 1
    assert len(second) == 1
    assert second[0]["region_type"] == "dimension_diagram"
    assert second[0]["provider"] == "manual"
    assert second[0]["crop_sha256"]


def test_api_does_not_return_absolute_paths(tmp_path):
    service = SimpleNamespace()
    task_id = uuid4()
    region_id = uuid4()

    async def create_task(revision_id, drawing_file, target_code, target_dn):
        return SimpleNamespace(id=task_id, revision_id=revision_id, status="created")

    async def start_layout(task_id):
        return {"task_id": str(task_id), "status": "created"}

    async def get_layout_status(task_id):
        return {"task_id": str(task_id), "status": "layout_ready", "error_code": None, "error_message": None}

    async def list_regions(task_id):
        return [
            {
                "id": str(region_id),
                "region_type": "parameter_table",
                "bbox_normalized": [0.1, 0.2, 0.9, 0.8],
                "bbox_pixels": [10, 20, 90, 80],
                "padded_bbox_pixels": [8, 18, 92, 82],
                "crop_sha256": "abc",
                "crop_width": 84,
                "crop_height": 64,
                "provider": "manual",
                "confidence": 1.0,
            }
        ]

    service.create_task = create_task
    service.start_layout = start_layout
    service.get_layout_status = get_layout_status
    service.list_regions = list_regions
    app.dependency_overrides[get_drawing_service] = lambda: service
    client = TestClient(app)

    response = client.get(f"/api/cad/spec/tasks/{task_id}/regions")

    app.dependency_overrides.pop(get_drawing_service, None)
    assert response.status_code == 200
    payload = response.json()
    assert "crop_file_path" not in payload["items"][0]
    assert "D:" not in response.text


def test_layout_endpoint_schedules_background_work(tmp_path, monkeypatch):
    service = SimpleNamespace()
    task_id = uuid4()
    scheduled = []

    async def get_task(_task_id):
        return SimpleNamespace(id=task_id)

    service.repository = SimpleNamespace(get_task=get_task)
    app.dependency_overrides[get_drawing_service] = lambda: service
    monkeypatch.setattr("app.drawing.router.schedule_layout_task", lambda scheduled_task_id, _settings: scheduled.append(scheduled_task_id))
    client = TestClient(app)

    response = client.post(f"/api/cad/spec/tasks/{task_id}/layout")

    app.dependency_overrides.pop(get_drawing_service, None)
    assert response.status_code == 202
    assert response.json()["status"] == "preprocessing_image"
    assert scheduled == [task_id]


def test_extract_endpoint_schedules_background_work(tmp_path, monkeypatch):
    service = SimpleNamespace()
    task_id = uuid4()
    scheduled = []

    async def get_task(_task_id):
        return SimpleNamespace(id=task_id)

    service.repository = SimpleNamespace(get_task=get_task)
    app.dependency_overrides[get_drawing_service] = lambda: service
    monkeypatch.setattr(
        "app.drawing.router.schedule_extraction_task",
        lambda scheduled_task_id, _settings, **kwargs: scheduled.append((scheduled_task_id, kwargs)),
    )
    client = TestClient(app)

    response = client.post(f"/api/cad/spec/tasks/{task_id}/extract", json={"target_code": "XMS06", "target_dn": 80, "force": True})

    app.dependency_overrides.pop(get_drawing_service, None)
    assert response.status_code == 202
    assert response.json()["status"] == "extracting_product_info"
    assert scheduled == [(task_id, {"target_code": "XMS06", "target_dn": 80, "force": True})]


@pytest.mark.asyncio
async def test_repeated_layout_does_not_create_duplicate_active_regions(tmp_path):
    image_path = make_image(tmp_path / "drawing.png", size=(300, 200))
    provider = ManualLayoutProvider([LayoutRegion("parameter_table", [30, 30, 260, 170], 1.0, "manual")])
    service = DrawingLayoutService(
        MemoryDrawingRepository(),
        work_dir=tmp_path / "work",
        provider=provider,
        max_image_mb=1,
        inference_max_side=200,
    )
    task = await service.create_task(revision_id=uuid4(), drawing_file=image_path, target_code=None, target_dn=None)

    await service.start_layout(task.id)
    await service.start_layout(task.id)
    regions = await service.list_regions(task.id)

    assert len(regions) == 1


@pytest.mark.asyncio
async def test_layout_status_remains_responsive_while_vision_layout_runs(tmp_path):
    image_path = make_image(tmp_path / "drawing.png", size=(300, 200))
    layout_started = asyncio.Event()
    release_layout = asyncio.Event()

    class SlowVisionProvider:
        async def detect(self, _image_path):
            layout_started.set()
            await release_layout.wait()
            return LayoutDetectionResult(
                "vision",
                "slow-test",
                "completed",
                [LayoutRegion("parameter_table", [20, 20, 170, 120], 1.0, "vision")],
            )

    service = DrawingLayoutService(
        MemoryDrawingRepository(),
        work_dir=tmp_path / "work",
        provider=SlowVisionProvider(),
        max_image_mb=1,
        inference_max_side=200,
    )
    task = await service.create_task(revision_id=uuid4(), drawing_file=image_path, target_code=None, target_dn=None)

    layout_task = asyncio.create_task(service.start_layout(task.id))
    await asyncio.wait_for(layout_started.wait(), timeout=1)
    started = time.perf_counter()
    status = await service.get_layout_status(task.id)
    elapsed = time.perf_counter() - started
    release_layout.set()
    await layout_task

    assert status["status"] == "detecting_layout"
    assert elapsed < 0.2
