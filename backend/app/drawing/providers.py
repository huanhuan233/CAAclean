from __future__ import annotations

import asyncio
import json
import shlex
import urllib.request
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from PIL import Image

from app.drawing.layout import LayoutDetectionResult, LayoutRegion, merge_regions, provider_type_to_region_type
from app.drawing.schemas import DrawingError


class LayoutProvider(Protocol):
    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        ...


class MineruLayoutProvider:
    def __init__(
        self,
        *,
        mode: str = "disabled",
        url: str | None = None,
        command: str | None = None,
        timeout: int = 180,
        transport: Callable[[Path], Awaitable[dict]] | None = None,
    ):
        self.mode = mode
        self.url = url
        self.command = command
        self.timeout = timeout
        self.transport = transport

    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        if self.mode == "disabled":
            raise DrawingError("mineru_not_configured", "MinerU layout provider is disabled")
        try:
            if self.transport:
                payload = await asyncio.wait_for(self.transport(image_path), timeout=self.timeout)
            elif self.mode == "http":
                payload = await asyncio.wait_for(asyncio.to_thread(self._http_detect, image_path), timeout=self.timeout)
            elif self.mode == "command":
                payload = await asyncio.wait_for(self._command_detect(image_path), timeout=self.timeout)
            else:
                raise DrawingError("mineru_not_configured", "unsupported MinerU layout mode")
        except TimeoutError as exc:
            raise DrawingError("mineru_timeout", "MinerU layout detection timed out") from exc
        except DrawingError:
            raise
        except Exception as exc:
            raise DrawingError("mineru_connection_failed", "MinerU layout detection failed") from exc
        return _parse_provider_payload(payload, provider="mineru")

    def _http_detect(self, image_path: Path) -> dict:
        if not self.url:
            raise DrawingError("mineru_not_configured", "MINERU_LAYOUT_URL is not configured")
        data = image_path.read_bytes()
        request = urllib.request.Request(self.url, data=data, method="POST", headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    async def _command_detect(self, image_path: Path) -> dict:
        if not self.command:
            raise DrawingError("mineru_not_configured", "MINERU_LAYOUT_COMMAND is not configured")
        args = [*shlex.split(self.command), str(image_path)]
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _stderr = await process.communicate()
        if process.returncode != 0:
            raise DrawingError("mineru_connection_failed", "MinerU command failed")
        return json.loads(stdout.decode("utf-8"))


class VisionLayoutProvider:
    provider_version = "heuristic.v1"

    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        return await asyncio.to_thread(self._detect_sync, image_path)

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


class ManualLayoutProvider:
    def __init__(self, regions: list[LayoutRegion]):
        self.regions = regions

    async def detect(self, image_path: Path) -> LayoutDetectionResult:
        return LayoutDetectionResult("manual", "manual.v1", "completed", self.regions)


class AutoLayoutProvider:
    def __init__(self, *, mineru: LayoutProvider, vision: LayoutProvider):
        self.mineru = mineru
        self.vision = vision

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
        except DrawingError as exc:
            warnings.append(exc.code)
            return LayoutDetectionResult("manual", "manual.v1", "needs_manual_layout", [], warnings=warnings)


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
        region_type = provider_type_to_region_type(provider_type, bbox, image_width=max(bbox[2], 1), image_height=max(bbox[3], 1))
        regions.append(LayoutRegion(region_type, bbox, raw.get("score") or raw.get("confidence"), provider, provider_type, raw_provider_result=raw))
    return LayoutDetectionResult(provider, payload.get("provider_version"), "completed", regions, raw_provider_result=payload)


def _is_ink(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return min(red, green, blue) < 245 and max(red, green, blue) - min(red, green, blue) > 5 or max(red, green, blue) < 230


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
