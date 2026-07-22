from __future__ import annotations

import uuid
from pathlib import Path

from app.drawing.cropper import PADDING_BY_REGION_TYPE, crop_regions
from app.drawing.layout import LayoutDetectionResult, LayoutRegion, merge_regions
from app.drawing.preprocessing import DrawingImagePreprocessor, sha256_file
from app.drawing.providers import LayoutProvider
from app.drawing.repository import MemoryRegion, copy_source_to_task_dir
from app.drawing.schemas import (
    DrawingCropPackage,
    DrawingError,
    ManualRegionIn,
    bbox_normalized_to_pixels,
    bbox_pixels_to_normalized,
)
from app.db.models import CadDrawingRegion


class DrawingLayoutService:
    def __init__(
        self,
        repository,
        *,
        work_dir: Path,
        provider: LayoutProvider,
        max_image_mb: int,
        max_side: int = 4096,
        inference_max_side: int,
        crop_padding: dict[str, float] | None = None,
        merge_gap_ratio: float = 0.02,
    ):
        self.repository = repository
        self.work_dir = Path(work_dir)
        self.provider = provider
        self.preprocessor = DrawingImagePreprocessor(max_image_mb=max_image_mb, max_side=max_side, inference_max_side=inference_max_side)
        self.crop_padding = crop_padding or PADDING_BY_REGION_TYPE
        self.merge_gap_ratio = merge_gap_ratio

    async def create_task(self, *, revision_id, drawing_file: Path, target_code: str | None, target_dn: str | None):
        source_path = copy_source_to_task_dir(Path(drawing_file), self.work_dir / "incoming" / str(uuid.uuid4()))
        return (
            await self.repository.create_task(
                revision_id=revision_id,
                source_path=source_path,
                source_sha256=sha256_file(source_path),
                mime_type=_mime_type(source_path),
                target_code=target_code,
                target_dn=target_dn,
            )
        )[0]

    async def start_layout(self, task_id: uuid.UUID) -> dict:
        task = await self.repository.get_task(task_id)
        source = await self.repository.get_source_for_task(task_id)
        if task is None or source is None:
            raise DrawingError("drawing_invalid", "drawing task not found")
        task_dir = self.work_dir / str(task_id)
        try:
            await self.repository.update_task_status(task_id, "preprocessing_image")
            preprocess = self.preprocessor.preprocess(Path(source.file_path), task_dir)
            await self.repository.update_source_metadata(source.id, preprocess.metadata() | {"inference_sha256": preprocess.inference_sha256})
            await self.repository.update_task_status(task_id, "detecting_layout")
            detection = await self.provider.detect(preprocess.inference_path)
            if detection.status == "needs_manual_layout":
                await self.repository.update_task_status(task_id, "needs_manual_layout", "manual_layout_required", "manual layout is required")
                return {"task_id": str(task_id), "status": "needs_manual_layout"}
            await self.repository.update_task_status(task_id, "cropping_regions")
            regions = []
            for region in detection.regions:
                bbox = region.bbox_pixels if region.provider == "manual" else preprocess.inference_to_original_bbox(region.bbox_pixels)
                regions.append(
                    LayoutRegion(
                        region.region_type,
                        bbox,
                        region.confidence,
                        region.provider,
                        provider_region_type=region.provider_region_type,
                        raw_provider_result=region.raw_provider_result,
                        metadata=region.metadata,
                    )
                )
            merged = merge_regions(regions, image_width=preprocess.original_width, image_height=preprocess.original_height, gap_ratio=self.merge_gap_ratio)
            await self._replace_with_crops(task_id, source.id, Path(source.file_path), merged, preprocess.original_width, preprocess.original_height)
            await self.repository.update_task_status(task_id, "layout_ready")
            return {"task_id": str(task_id), "status": "layout_ready"}
        except DrawingError as exc:
            await self.repository.update_task_status(task_id, "failed", exc.code, exc.message)
            raise

    async def get_layout_status(self, task_id: uuid.UUID) -> dict:
        task = await self.repository.get_task(task_id)
        if task is None:
            raise DrawingError("drawing_invalid", "drawing task not found")
        return {"task_id": task.id, "status": task.status, "error_code": task.error_code, "error_message": task.error_message}

    async def list_regions(self, task_id: uuid.UUID) -> list[dict]:
        return [self._region_to_dict(region) for region in await self.repository.list_active_regions(task_id)]

    async def apply_manual_regions(self, task_id: uuid.UUID, regions: list[ManualRegionIn]) -> dict:
        task = await self.repository.get_task(task_id)
        source = await self.repository.get_source_for_task(task_id)
        if task is None or source is None:
            raise DrawingError("drawing_invalid", "drawing task not found")
        preprocess = self.preprocessor.preprocess(Path(source.file_path), self.work_dir / str(task_id))
        layout_regions = [
            LayoutRegion(
                region.region_type,
                bbox_normalized_to_pixels(region.bbox_normalized, width=preprocess.original_width, height=preprocess.original_height),
                region.confidence if region.confidence is not None else 1.0,
                "manual",
                provider_region_type="manual",
            )
            for region in regions
        ]
        await self._replace_with_crops(task_id, source.id, Path(source.file_path), layout_regions, preprocess.original_width, preprocess.original_height)
        await self.repository.update_task_status(task_id, "layout_ready")
        return {"task_id": str(task_id), "status": "layout_ready"}

    async def build_crop_package(self, task_id: uuid.UUID) -> DrawingCropPackage:
        source = await self.repository.get_source_for_task(task_id)
        regions = await self.list_regions(task_id)
        metadata = getattr(source, "metadata_json", None) or getattr(source, "metadata", {})
        return DrawingCropPackage(
            task_id=task_id,
            source_id=source.id,
            original_image={
                "width": metadata.get("original_width"),
                "height": metadata.get("original_height"),
                "sha256": source.sha256,
            },
            inference_image={
                "width": metadata.get("inference_width"),
                "height": metadata.get("inference_height"),
                "sha256": metadata.get("inference_sha256"),
            },
            layout={"provider": regions[0]["provider"] if regions else "manual", "provider_version": None, "status": "layout_ready"},
            regions=regions,
            warnings=[],
        )

    async def _replace_with_crops(self, task_id, source_id, image_path: Path, regions: list[LayoutRegion], width: int, height: int) -> None:
        crops = crop_regions(image_path, regions, self.work_dir, task_id, padding_by_region_type=self.crop_padding)
        rows = []
        for index, crop in enumerate(crops):
            normalized = bbox_pixels_to_normalized(crop.region.bbox_pixels, width=width, height=height)
            rows.append(
                self._make_region_row(
                    task_id=task_id,
                    source_id=source_id,
                    region_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{task_id}:{index}:{crop.region.region_type}:{crop.region.bbox_pixels}"),
                    region_type=crop.region.region_type,
                    provider=crop.region.provider,
                    provider_region_type=crop.region.provider_region_type,
                    bbox_normalized=normalized,
                    bbox_pixels=crop.region.bbox_pixels,
                    padded_bbox_pixels=crop.padded_bbox_pixels,
                    confidence=crop.region.confidence,
                    sort_order=index,
                    crop_file_path=str(crop.crop_file_path),
                    crop_file_name=crop.crop_file_name,
                    crop_sha256=crop.crop_sha256,
                    crop_width=crop.crop_width,
                    crop_height=crop.crop_height,
                    raw_provider_result=crop.region.raw_provider_result,
                    metadata={"mime_type": crop.mime_type},
                )
            )
        await self.repository.replace_regions(task_id, rows)

    def _make_region_row(self, **kwargs):
        kwargs["id"] = kwargs.pop("region_id")
        if self.repository.__class__.__name__ == "MemoryDrawingRepository":
            return MemoryRegion(metadata_json=kwargs.pop("metadata"), **kwargs)
        return CadDrawingRegion(metadata_json=kwargs.pop("metadata"), **kwargs)

    def _region_to_dict(self, region) -> dict:
        return {
            "id": region.id,
            "region_type": region.region_type,
            "bbox_normalized": region.bbox_normalized,
            "bbox_pixels": region.bbox_pixels,
            "padded_bbox_pixels": region.padded_bbox_pixels,
            "crop_sha256": region.crop_sha256,
            "crop_width": region.crop_width,
            "crop_height": region.crop_height,
            "provider": region.provider,
            "confidence": region.confidence,
        }


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
