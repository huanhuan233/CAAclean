from pathlib import Path

import pytest
from PIL import Image

from app.drawing.extraction_client import VisionModelError
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.image_utils import prepare_patent_images
from app.patent_annotation.localization import PatentLocalizationService
from app.patent_annotation.schemas import LocalizationCandidate


def test_prepare_patent_images_applies_exif_rotation(tmp_path):
    path = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (40, 80), "white")
    exif = Image.Exif()
    exif[274] = 6
    image.save(path, format="JPEG", exif=exif)

    assets = prepare_patent_images(path, tmp_path / "work", max_image_mb=1, max_side=100)

    assert assets.width == 80
    assert assets.height == 40


def test_prepare_patent_images_composites_alpha_on_white(tmp_path):
    path = tmp_path / "alpha.png"
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    image.putpixel((10, 10), (255, 0, 0, 255))
    image.save(path)

    assets = prepare_patent_images(path, tmp_path / "work", max_image_mb=1, max_side=100)
    cleaned = Image.open(assets.clean_path)

    assert cleaned.mode == "RGB"
    assert cleaned.getpixel((0, 0)) == (255, 255, 255)


def test_prepare_patent_images_resizes_longest_side_and_grid_matches(tmp_path):
    path = tmp_path / "large.png"
    Image.new("RGB", (400, 200), "white").save(path)

    assets = prepare_patent_images(path, tmp_path / "work", max_image_mb=1, max_side=100)

    assert (assets.width, assets.height) == (100, 50)
    assert Image.open(assets.clean_path).size == (100, 50)
    assert Image.open(assets.grid_path).size == (100, 50)


def test_prepare_patent_images_rejects_bad_and_oversized_input(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")

    with pytest.raises(PatentAnnotationError) as bad_exc:
        prepare_patent_images(bad, tmp_path / "bad-work", max_image_mb=1)
    assert bad_exc.value.code == "patent_image_decode_failed"

    large = tmp_path / "large.png"
    Image.new("RGB", (10, 10), "white").save(large)
    with pytest.raises(PatentAnnotationError) as large_exc:
        prepare_patent_images(large, tmp_path / "large-work", max_image_mb=0)
    assert large_exc.value.code == "patent_image_too_large"


class FakeVisionClient:
    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls = []

    async def complete_json(self, *, task_name, schema, messages, image_paths):
        self.calls.append({"task_name": task_name, "schema": schema, "messages": messages, "image_paths": image_paths})
        if self.error:
            raise self.error
        return self.outputs.pop(0)


def candidate(ref_no, name="part"):
    return LocalizationCandidate(ref_no=ref_no, name=name)


@pytest.mark.asyncio
async def test_localize_normalizes_anchor_and_accepts_high_confidence(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    client = FakeVisionClient(
        [{"items": [{"ref_no": "68", "visible": True, "confidence": 0.95, "anchor": {"x": 250, "y": 750}}]}]
    )
    service = PatentLocalizationService(client, model_name="vision-test")

    result = await service.localize(
        image_path,
        figure_no="4",
        figure_description="partial figure",
        figure_context="spring 68",
        candidates=[candidate("68", "spring")],
        work_dir=tmp_path / "work",
    )

    assert result.items[0].anchor.x == 0.25
    assert result.items[0].anchor.y == 0.75
    assert result.items[0].review_state == "accepted"
    assert client.calls[0]["task_name"] == "patent_page_localization"
    assert len(client.calls[0]["image_paths"]) == 2


@pytest.mark.asyncio
async def test_localize_filters_unknown_refs_and_keeps_highest_duplicate(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    client = FakeVisionClient(
        [
            {
                "items": [
                    {"ref_no": "1", "visible": True, "confidence": 0.4, "anchor": {"x": 100, "y": 100}},
                    {"ref_no": "1", "visible": True, "confidence": 0.9, "anchor": {"x": 300, "y": 400}},
                    {"ref_no": "9", "visible": True, "confidence": 1, "anchor": {"x": 500, "y": 500}},
                ]
            }
        ]
    )

    result = await PatentLocalizationService(client).localize(
        image_path,
        figure_no="1",
        figure_description="",
        figure_context="",
        candidates=[candidate("1")],
        work_dir=tmp_path / "work",
    )

    assert [item.ref_no for item in result.items] == ["1"]
    assert result.items[0].anchor.x == 0.3
    assert "unknown_ref_9" in result.warnings


@pytest.mark.asyncio
async def test_localize_repairs_invalid_visibility_and_bbox_states(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    client = FakeVisionClient(
        [
            {
                "items": [
                    {"ref_no": "1", "visible": True, "confidence": 0.9},
                    {
                        "ref_no": "2",
                        "visible": True,
                        "confidence": 0.9,
                        "anchor": {"x": 900, "y": 900},
                        "bbox": {"x_min": 800, "y_min": 800, "x_max": 200, "y_max": 200},
                    },
                    {"ref_no": "3", "visible": True, "confidence": 0.2, "anchor": {"x": 100, "y": 100}},
                ]
            }
        ]
    )

    result = await PatentLocalizationService(client).localize(
        image_path,
        figure_no="1",
        figure_description="",
        figure_context="",
        candidates=[candidate("1"), candidate("2"), candidate("3")],
        work_dir=tmp_path / "work",
    )

    by_ref = {item.ref_no: item for item in result.items}
    assert by_ref["1"].visible is False
    assert by_ref["1"].review_state == "rejected"
    assert by_ref["2"].bbox.x_min == 0.2
    assert by_ref["2"].bbox.x_max == 0.8
    assert by_ref["2"].review_state == "review"
    assert by_ref["3"].review_state == "rejected"
    assert "visible_without_anchor_1" in result.warnings
    assert "anchor_outside_bbox_2" in result.warnings


@pytest.mark.asyncio
async def test_localize_clamps_out_of_range_model_coordinates(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    client = FakeVisionClient(
        [
            {
                "items": [
                    {
                        "ref_no": "1",
                        "visible": True,
                        "confidence": 0.9,
                        "anchor": {"x": -50, "y": 1200},
                        "bbox": {"x_min": -20, "y_min": 0, "x_max": 1500, "y_max": 1000},
                    }
                ]
            }
        ]
    )

    result = await PatentLocalizationService(client).localize(
        image_path,
        figure_no="1",
        figure_description="",
        figure_context="",
        candidates=[candidate("1")],
        work_dir=tmp_path / "work",
    )

    assert result.items[0].anchor.x == 0
    assert result.items[0].anchor.y == 1
    assert result.items[0].bbox.x_max == 1


@pytest.mark.asyncio
async def test_localize_batches_candidates_in_groups_of_16(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    client = FakeVisionClient([{"items": []}, {"items": []}])
    candidates = [candidate(str(index)) for index in range(17)]

    await PatentLocalizationService(client).localize(
        image_path,
        figure_no="1",
        figure_description="",
        figure_context="",
        candidates=candidates,
        work_dir=tmp_path / "work",
    )

    assert len(client.calls) == 2
    assert '"15"' in client.calls[0]["messages"][0]["text"]
    assert '"16"' in client.calls[1]["messages"][0]["text"]


@pytest.mark.asyncio
async def test_localize_propagates_vision_model_error(tmp_path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    service = PatentLocalizationService(
        FakeVisionClient(error=VisionModelError("vision_request_failed", "bad")),
    )

    with pytest.raises(VisionModelError) as exc:
        await service.localize(
            image_path,
            figure_no="1",
            figure_description="",
            figure_context="",
            candidates=[candidate("1")],
            work_dir=tmp_path / "work",
        )

    assert exc.value.code == "vision_request_failed"
