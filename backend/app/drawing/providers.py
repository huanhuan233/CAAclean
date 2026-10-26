# 提供 MinerU、像素带启发式及人工版面入口，并支持自动降级到人工框选。
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from PIL import Image

from app.core.mineru import MineruClient, MineruError
from app.drawing.layout import LayoutDetectionResult, LayoutRegion, merge_regions, provider_type_to_region_type
from app.drawing.schemas import DrawingError


# 约定异步版面检测入口，统一返回区域、状态和诊断信息。
class LayoutProvider(Protocol):
    # 供应商须接收图像路径并返回统一版面结果。
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        ...


# 将 MinerU 的传输协议和响应转换为内部版面模型。
class MineruLayoutProvider:
    # 配置 MinerU 运行方式、端点或命令、超时及可替换传输函数。
    def __init__(
        self,
        *,
        mode: str = "disabled",
        url: str | None = None,
        command: str | None = None,
        timeout: int = 180,
        transport: Callable[[Path], Awaitable[dict]] | None = None,
    ):
        self.client = MineruClient(
            mode=mode,
            url=url,
            command=command,
            timeout=timeout,
            transport=transport,
        )

    # 取得供应商响应并解析区域，将 MinerU 错误保留为图纸业务错误。
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        try:
            payload = await self.client.fetch_payload(image_path)
        except MineruError as exc:
            raise DrawingError(exc.code, exc.message) from exc
        return _parse_provider_payload(payload, provider="mineru")


# 基于像素墨迹行带定位区域的启发式供应商；此类本身不执行 OCR 或视觉模型调用。
class VisionLayoutProvider:
    provider_version = "heuristic.v1"

    # 在线程中执行像素扫描，避免同步图像遍历阻塞异步事件循环。
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        return await asyncio.to_thread(self._detect_sync, image_path)

    # 统计墨迹行并分带，按区域高度与位置分类；无有效区域时报告失败。
    def _detect_sync(self, image_path: Path) -> LayoutDetectionResult:
        try:
            with Image.open(image_path) as image:
                rgb = image.convert("RGB")
                width, height = rgb.size
                pixels = rgb.load()
                row_counts: list[int] = []
                row_bounds: list[tuple[int, int] | None] = []
                for y in range(height):
                    xs = [x for x in range(width) if _is_ink(pixels[x, y])]
                    row_counts.append(len(xs))
                    row_bounds.append((min(xs), max(xs) + 1) if xs else None)
        except OSError as exc:
            raise DrawingError("vision_layout_failed", "vision layout image decode failed") from exc

        threshold = max(3, round(width * 0.005))
        bands = _row_bands(row_counts, threshold=threshold, merge_gap=max(2, round(height * 0.03)))
        regions: list[LayoutRegion] = []
        for y_min, y_max in bands:
            xs_min = [row_bounds[y][0] for y in range(y_min, y_max) if row_bounds[y]]
            xs_max = [row_bounds[y][1] for y in range(y_min, y_max) if row_bounds[y]]
            if not xs_min:
                continue
            bbox = [min(xs_min), y_min, max(xs_max), y_max]
            region_type = _classify_band(bbox, width=width, height=height)
            if region_type == "unknown":
                continue
            regions.append(LayoutRegion(region_type, bbox, 0.72, "vision", provider_region_type="heuristic_band"))
        merged = merge_regions(regions, image_width=width, image_height=height, gap_ratio=0.02) if regions else []
        if not merged:
            raise DrawingError("vision_layout_failed", "vision layout found no regions")
        return LayoutDetectionResult("vision", self.provider_version, "completed", merged)


# 直接提供调用方给定的人工区域。
class ManualLayoutProvider:
    # 保存已构造的人工区域，不在此阶段校验图像边界。
    def __init__(self, regions: list[LayoutRegion]):
        self.regions = regions

    # 返回固定人工区域列表，图像路径在此实现中不参与处理。
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        return LayoutDetectionResult("manual", "manual.v1", "completed", self.regions)


# 优先使用 MinerU，其次尝试像素启发式，均失败时要求人工布局。
class AutoLayoutProvider:
    # 注入主供应商和备用供应商以组合降级路径。
    def __init__(self, *, mineru: LayoutProvider, vision: LayoutProvider):
        self.mineru = mineru
        self.vision = vision

    # 保留已捕获的业务错误码为警告，最终以 needs_manual_layout 表达无自动结果。
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        warnings = []
        try:
            result = await self.mineru.detect(image_path)
            if result.regions:
                return result
        except DrawingError as exc:
            warnings.append(exc.code)
        try:
            result = await self.vision.detect(image_path)
            result.warnings.extend(warnings)
            return result
        # 两条自动路径均无结果时保留错误码，并把后续操作交给人工框选。
        except DrawingError as exc:
            warnings.append(exc.code)
            return LayoutDetectionResult("manual", "manual.v1", "needs_manual_layout", [], warnings=warnings)


# 兼容 regions/layout 与 bbox/box 键，保留原始记录并检查坐标数量。
def _parse_provider_payload(payload: dict, *, provider: str) -> LayoutDetectionResult:
    raw_regions = payload.get("regions") or payload.get("layout") or []
    if not raw_regions:
        raise DrawingError("layout_no_regions", "layout provider returned no regions")
    regions = []
    for raw in raw_regions:
        bbox = [int(round(value)) for value in raw.get("bbox") or raw.get("box") or []]
        if len(bbox) != 4:
            raise DrawingError("mineru_invalid_result", "provider region missing bbox")
        provider_type = raw.get("type") or raw.get("category")
        # 此响应适配未取得整图尺寸，暂以当前框右下角作为位置分类的宽高参考。
        region_type = provider_type_to_region_type(provider_type, bbox, image_width=max(bbox[2], 1), image_height=max(bbox[3], 1))
        regions.append(LayoutRegion(region_type, bbox, raw.get("score") or raw.get("confidence"), provider, provider_type, raw_provider_result=raw))
    return LayoutDetectionResult(provider, payload.get("provider_version"), "completed", regions, raw_provider_result=payload)


# 按亮度和通道差判断像素是否为墨迹，过滤接近白色的背景。
def _is_ink(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return min(red, green, blue) < 245 and max(red, green, blue) - min(red, green, blue) > 5 or max(red, green, blue) < 230


# 将达到墨迹阈值的连续行合并为半开区间，允许短空白间隙。
def _row_bands(row_counts: list[int], *, threshold: int, merge_gap: int) -> list[tuple[int, int]]:
    bands = []
    start = None
    last = None
    for y, count in enumerate(row_counts):
        if count >= threshold:
            if start is None:
                start = y
            last = y
        elif start is not None and last is not None and y - last > merge_gap:
            bands.append((start, last + 1))
            start = None
            last = None
    if start is not None and last is not None:
        bands.append((start, last + 1))
    return bands


# 用页面位置、带宽和带高估计产品信息、表格或示意图，无法判定则返回 unknown。
def _classify_band(bbox: list[int], *, width: int, height: int) -> str:
    x_min, y_min, x_max, y_max = bbox
    band_height = y_max - y_min
    if y_max <= height * 0.18:
        return "product_information"
    if y_min >= height * 0.55 and band_height >= height * 0.12:
        return "parameter_table"
    if band_height < height * 0.08:
        return "notes"
    if y_min < height * 0.58 and x_max - x_min >= width * 0.15:
        return "dimension_diagram"
    return "unknown"
