import asyncio
import json
import os
import time
from pathlib import Path

from app.core.config import Settings
from app.patent_annotation.router import get_document_parser, get_localization_service
from app.patent_annotation.schemas import LocalizationCandidate


async def main() -> None:
    specification = Path(os.environ["PATENT_SPECIFICATION_PDF"])
    image_dir = Path(os.environ["PATENT_FIGURE_IMAGE_DIR"])
    settings = Settings()
    parser = get_document_parser(settings)
    localization = get_localization_service(settings)

    parse_started = time.monotonic()
    parsed = await parser.parse(specification, file_name=specification.name, fast=False)
    components = [
        LocalizationCandidate(ref_no=item.ref_no, name=item.name)
        for item in parsed.components
    ]
    summary = {
        "parser": parsed.parser,
        "document_context_chars": len(parsed.document_context),
        "component_refs": [item.ref_no for item in parsed.components],
        "parse_seconds": round(time.monotonic() - parse_started, 1),
        "figures": [],
    }

    for image_path in sorted(image_dir.glob("figure-*.png")):
        figure_no = image_path.stem.rsplit("-", 1)[-1]
        figure = next((item for item in parsed.figures if item.figure_no == figure_no), None)
        started = time.monotonic()
        result = await localization.localize(
            image_path,
            figure_no=figure_no,
            figure_description=figure.description if figure else "",
            figure_context=figure.context if figure else "",
            document_context=parsed.document_context,
            candidates=components,
            work_dir=image_dir / f"work-{figure_no}",
        )
        visible = [
            {
                "ref_no": item.ref_no,
                "name": item.name,
                "anchor": item.anchor.model_dump() if item.anchor else None,
                "confidence": item.confidence,
                "review_state": item.review_state,
            }
            for item in result.items
            if item.visible and item.anchor is not None
        ]
        summary["figures"].append(
            {
                "figure_no": figure_no,
                "returned_items": len(result.items),
                "coordinate_count": len(visible),
                "visible": visible,
                "warnings": result.warnings,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
    print(json.dumps(summary, ensure_ascii=False))


asyncio.run(main())
