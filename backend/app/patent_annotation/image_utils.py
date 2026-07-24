from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from app.patent_annotation.errors import PatentAnnotationError


@dataclass(frozen=True)
class PatentImageAssets:
    clean_path: Path
    grid_path: Path
    width: int
    height: int


def prepare_patent_images(
    source: Path,
    output_dir: Path,
    *,
    max_image_mb: int = 20,
    max_side: int = 2048,
) -> PatentImageAssets:
    source = Path(source)
    output_dir = Path(output_dir)
    if source.stat().st_size > max_image_mb * 1024 * 1024:
        raise PatentAnnotationError("patent_image_too_large", "patent image is too large")

    try:
        with Image.open(source) as opened:
            if opened.format not in {"PNG", "JPEG", "WEBP"}:
                raise PatentAnnotationError("patent_image_invalid", "only PNG, JPG, JPEG, or WEBP images are supported")
            image = ImageOps.exif_transpose(opened)
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                image = image.convert("RGBA")
                background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                background.alpha_composite(image)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")
    except PatentAnnotationError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise PatentAnnotationError("patent_image_decode_failed", "patent image cannot be decoded") from exc

    longest_side = max(image.size)
    if longest_side > max_side:
        ratio = max_side / longest_side
        image = image.resize(
            (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    image = ImageOps.autocontrast(image, cutoff=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "clean.png"
    grid_path = output_dir / "coordinate-grid.png"
    image.save(clean_path, format="PNG")
    shutil.copyfile(clean_path, grid_path)
    _draw_coordinate_grid(grid_path)
    return PatentImageAssets(clean_path=clean_path, grid_path=grid_path, width=image.width, height=image.height)


def _draw_coordinate_grid(path: Path) -> None:
    with Image.open(path) as image:
        grid = image.convert("RGB")
    draw = ImageDraw.Draw(grid)
    width, height = grid.size
    line_color = (180, 210, 255)
    text_color = (70, 90, 130)
    for value in range(0, 1001, 100):
        x = round(value / 1000 * (width - 1)) if width > 1 else 0
        y = round(value / 1000 * (height - 1)) if height > 1 else 0
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
    for value in range(0, 1001, 250):
        x = round(value / 1000 * (width - 1)) if width > 1 else 0
        y = round(value / 1000 * (height - 1)) if height > 1 else 0
        draw.text((min(x + 2, max(0, width - 24)), 1), str(value), fill=text_color)
        draw.text((1, min(y + 2, max(0, height - 10))), str(value), fill=text_color)
    grid.save(path, format="PNG")
