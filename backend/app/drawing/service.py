# 编排图纸任务从原图归档、版面分析、裁剪到事实提取，统一提供证据查询接口。
from __future__ import annotations

import uuid
from collections.abc import Callable
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
from app.drawing.extraction_service import DrawingExtractionService


# 组合仓库、预处理器、版面供应商与延迟初始化的视觉客户端。
class DrawingLayoutService:
    # 保存图像与裁剪配置，并允许分别注入布局和事实仓库。
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
        extraction_repository=None,
        vision_client=None,
    ):
        self.repository = repository
        self.work_dir = Path(work_dir)
        self.provider = provider
        self.preprocessor = DrawingImagePreprocessor(max_image_mb=max_image_mb, max_side=max_side, inference_max_side=inference_max_side)
        self.crop_padding = crop_padding or PADDING_BY_REGION_TYPE
        self.merge_gap_ratio = merge_gap_ratio
        self._extraction_repository = extraction_repository or repository
        self.vision_client = vision_client
        self._resolved_vision_client = None

    # 先归档上传源图并计算摘要，再创建关联修订的图纸任务。
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

    # 为任务列表补充最新源文件名、进度和状态消息。
    async def list_tasks(self, revision_id: uuid.UUID | None = None) -> dict:
        tasks = await self.repository.list_tasks(revision_id=revision_id)
        items = []
        for task in tasks:
            source = await self.repository.get_source_for_task(task.id)
            items.append(
                {
                    "task_id": task.id,
                    "revision_id": task.revision_id,
                    "status": task.status,
                    "progress": getattr(task, "progress", 0),
                    "status_message": getattr(task, "status_message", None),
                    "file_name": getattr(source, "file_name", None) if source else None,
                    "created_at": getattr(task, "created_at", None),
                }
            )
        return {"items": items, "total": len(items)}

    # 执行预处理、检测、坐标回映、区域合并和裁剪，业务失败写入任务状态。
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
                # 自动供应商检测的是缩小推理图，人工框则约定已经位于原图像素坐标系。
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

    # 返回布局任务状态；任务不存在时抛出 drawing_invalid。
    async def get_layout_status(self, task_id: uuid.UUID) -> dict:
        task = await self.repository.get_task(task_id)
        if task is None:
            raise DrawingError("drawing_invalid", "drawing task not found")
        return {"task_id": task.id, "status": task.status, "error_code": task.error_code, "error_message": task.error_message}

    # 将当前有效区域转换为接口使用的字典列表。
    async def list_regions(self, task_id: uuid.UUID) -> list[dict]:
        return [self._region_to_dict(region) for region in await self.repository.list_active_regions(task_id)]

    # 把人工归一化框转换为原图框，重新裁剪并将任务标记为布局就绪。
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

    # 汇总源图元数据与有效区域路径，构造视觉提取所需证据包。
    async def build_crop_package(self, task_id: uuid.UUID) -> DrawingCropPackage:
        source = await self.repository.get_source_for_task(task_id)
        region_rows = await self.repository.list_active_regions(task_id)
        regions = [self._region_to_dict(region) | {"crop_file_path": region.crop_file_path} for region in region_rows]
        # 包内原图宽高依赖源记录的预处理元数据，调用方应先完成对应布局流程。
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
                "file_path": str(Path(self.work_dir) / str(task_id) / "whole_inference.png"),
            },
            layout={"provider": regions[0]["provider"] if regions else "manual", "provider_version": None, "status": "layout_ready"},
            regions=regions,
            warnings=[],
        )

    # 生成裁剪文件并映射为区域记录，按任务、顺序、类别与坐标生成稳定 UUID。
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

    # 按仓库类型选择内存或 ORM 区域记录，并统一元数据字段名。
    def _make_region_row(self, **kwargs):
        kwargs["id"] = kwargs.pop("region_id")
        if self.repository.__class__.__name__ == "MemoryDrawingRepository":
            return MemoryRegion(metadata_json=kwargs.pop("metadata"), **kwargs)
        return CadDrawingRegion(metadata_json=kwargs.pop("metadata"), **kwargs)

    # 导出区域坐标、摘要、尺寸和来源，文件路径由调用方按用途追加。
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

    # 调用提取编排器，任何异常均先写入 failed 状态再向上抛出。
    async def extract_drawing_facts(self, task_id: uuid.UUID, *, target_code: str | None = None, target_dn: int | None = None, force: bool = False):
        try:
            return await self.extraction_service.extract(task_id, target_code=target_code, target_dn=target_dn, force=force)
        except Exception as exc:
            code = getattr(exc, "code", "drawing_extraction_failed")
            message = getattr(exc, "message", "drawing extraction failed")
            await self.extraction_repository.set_status(task_id, "failed", 100, "failed", code, message)
            raise

    # 透传事实仓库保存的提取状态。
    async def get_extraction_status(self, task_id: uuid.UUID):
        return await self.extraction_repository.get_status(task_id)

    # 返回 JSON 兼容提取结果，尚未生成时报告结果不存在。
    async def get_extraction_result(self, task_id: uuid.UUID):
        result = await self.extraction_repository.get_result(task_id)
        if result is None:
            raise DrawingError("drawing_extraction_not_found", "drawing extraction result not found")
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return result

    # 传递筛选和分页条件，并统一内存模型与数据库行的输出结构。
    async def list_drawing_facts(
        self,
        task_id: uuid.UUID,
        *,
        fact_type: str | None = None,
        symbol: str | None = None,
        needs_review: bool | None = None,
        keyword: str | None = None,
        target_code: str | None = None,
        target_dn: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        rows, total = await self.extraction_repository.list_facts(
            task_id,
            fact_type=fact_type,
            symbol=symbol,
            needs_review=needs_review,
            keyword=keyword,
            target_code=target_code,
            target_dn=target_dn,
            page=page,
            page_size=page_size,
        )
        return {"items": [self._fact_to_dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    # 仅允许失败或待复核状态重新提取，避免在中间阶段发起重试。
    async def retry_extraction(self, task_id: uuid.UUID):
        status = await self.extraction_repository.get_status(task_id)
        if status["status"] not in {"failed", "review_ready"}:
            raise DrawingError("drawing_extraction_retry_not_allowed", "retry is only allowed after failed or review_ready")
        return await self.extract_drawing_facts(task_id, force=True)

    # 使用当前事实仓库和已解析视觉客户端构建提取服务。
    @property
    def extraction_service(self):
        return DrawingExtractionService(self.extraction_repository, vision_client=self._get_vision_client())

    # 暴露负责提取状态和事实存储的仓库。
    @property
    def extraction_repository(self):
        return self._extraction_repository

    # 首次访问时调用客户端工厂并缓存，后续复用同一实例。
    def _get_vision_client(self):
        if self._resolved_vision_client is not None:
            return self._resolved_vision_client
        if isinstance(self.vision_client, Callable):
            self._resolved_vision_client = self.vision_client()
        else:
            self._resolved_vision_client = self.vision_client
        return self._resolved_vision_client

    # 统一序列化图纸事实，保留原始值、数值、来源框与复核标记。
    def _fact_to_dict(self, row) -> dict:
        if hasattr(row, "model_dump"):
            return row.model_dump(mode="json")
        return {
            "id": row.id,
            "fact_key": row.fact_key,
            "fact_type": row.fact_type,
            "symbol": row.symbol,
            "label": row.label,
            "operator": row.operator,
            "raw_value": row.raw_value,
            "normalized_value": row.normalized_value,
            "value_type": row.value_type,
            "unit": row.unit,
            "source_region_id": row.region_id,
            "source_bbox_original": row.source_bbox_original,
            "source_bbox_normalized": row.source_bbox_normalized,
            "source_bbox_precision": row.source_bbox_precision,
            "confidence": row.confidence,
            "needs_review": row.needs_review,
            "metadata": row.metadata_json,
        }


# 按支持的图像后缀选择媒体类型，其他后缀默认标为 PNG。
def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
