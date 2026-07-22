from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.drawing.schemas import DrawingError, PreprocessResult


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DrawingImagePreprocessor:
    def __init__(self, *, max_image_mb: int = 20, max_side: int = 4096, inference_max_side: int = 2048):
        self.max_image_mb = max_image_mb
        self.max_side = max_side
        self.inference_max_side = inference_max_side

    def preprocess(self, image_path: Path, output_dir: Path) -> PreprocessResult:
        image_path = Path(image_path)
        if image_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise DrawingError("drawing_invalid", "unsupported drawing image type")
        if not image_path.exists() or image_path.stat().st_size == 0:
            raise DrawingError("drawing_invalid", "drawing image is empty")
        if image_path.stat().st_size > self.max_image_mb * 1024 * 1024:
            raise DrawingError("drawing_too_large", "drawing image exceeds configured size limit")

        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(image_path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise DrawingError("drawing_decode_failed", "drawing image cannot be decoded") from exc

        width, height = image.size
        if width <= 0 or height <= 0:
            raise DrawingError("drawing_decode_failed", "drawing image has invalid dimensions")
        if max(width, height) > self.max_side:
            raise DrawingError("drawing_too_large", "drawing image dimensions exceed configured side limit")

        inference = image.copy()
        if max(width, height) > self.inference_max_side:
            scale = self.inference_max_side / max(width, height)
            inference = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)

        inference_path = output_dir / "whole_inference.png"
        inference.save(inference_path, format="PNG")
        inference_width, inference_height = inference.size
        return PreprocessResult(
            original_path=image_path,
            inference_path=inference_path,
            original_width=width,
            original_height=height,
            inference_width=inference_width,
            inference_height=inference_height,
            original_sha256=sha256_file(image_path),
            inference_sha256=sha256_file(inference_path),
            scale_original_to_inference_x=inference_width / width,
            scale_original_to_inference_y=inference_height / height,
            scale_inference_to_original_x=width / inference_width,
            scale_inference_to_original_y=height / inference_height,
        )
