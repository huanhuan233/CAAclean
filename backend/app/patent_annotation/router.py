from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import TypeAdapter, ValidationError

from app.core.config import Settings, get_settings
from app.core.mineru import MineruClient, MineruDocumentClient
from app.core.vision import build_vision_client
from app.drawing.extraction_client import VisionModelError
from app.patent_annotation.document_parser import PatentDocumentParser
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.localization import PatentLocalizationService
from app.patent_annotation.schemas import LocalizationCandidate, NormalizedLocalizationResult, PatentDocumentParseResult


router = APIRouter(prefix="/api/patent-annotations", tags=["patent-annotations"])
PDF_MAX_BYTES = 30 * 1024 * 1024
IMAGE_MAX_BYTES = 20 * 1024 * 1024
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def get_document_parser(settings: Settings = Depends(get_settings)) -> PatentDocumentParser:
    if settings.mineru_api_url.strip():
        return PatentDocumentParser(
            mineru_client=MineruDocumentClient(
                api_url=settings.mineru_api_url,
                endpoint=settings.mineru_parse_endpoint,
                backend=settings.mineru_backend,
                ocr_lang=settings.mineru_ocr_lang,
                result_mode=settings.mineru_result_mode,
                enable_table=settings.mineru_enable_table,
                enable_formula=settings.mineru_enable_formula,
                enable_image_analysis=settings.mineru_enable_image_analysis,
                enable_ocr=settings.mineru_enable_ocr,
                server_url=settings.mineru_vlm_url or None,
                timeout=settings.mineru_request_timeout,
            )
        )
    return PatentDocumentParser(
        mineru_client=MineruClient(
            mode=settings.mineru_layout_mode,
            url=settings.mineru_layout_url or None,
            command=settings.mineru_layout_command or None,
            timeout=settings.mineru_layout_timeout,
        )
    )


def get_localization_service(settings: Settings = Depends(get_settings)) -> PatentLocalizationService:
    if not settings.vision_model or not settings.vision_binding_host or not settings.vision_binding_api_key:
        raise _http_error(PatentAnnotationError("vision_not_configured", "vision model is not configured"))
    return PatentLocalizationService(build_vision_client(settings), model_name=settings.vision_model)


@router.post("/parse-document", response_model=PatentDocumentParseResult)
async def parse_document(
    fast: bool = Form(False),
    pdf_file: UploadFile = File(...),
    parser: PatentDocumentParser = Depends(get_document_parser),
):
    try:
        _validate_pdf_upload(pdf_file)
        data = await _read_limited(pdf_file, PDF_MAX_BYTES, too_large_code="patent_pdf_too_large")
        if not data:
            raise PatentAnnotationError("patent_pdf_empty", "PDF file is empty")
        with tempfile.TemporaryDirectory(prefix="patent-pdf-") as temp_dir:
            path = Path(temp_dir) / (pdf_file.filename or "document.pdf")
            path.write_bytes(data)
            return await parser.parse(path, file_name=pdf_file.filename or path.name, fast=fast)
    except (PatentAnnotationError, VisionModelError) as exc:
        raise _http_error(exc) from exc


@router.post("/localize-page", response_model=NormalizedLocalizationResult)
async def localize_page(
    figure_no: str = Form(...),
    figure_description: str = Form(default=""),
    figure_context: str = Form(default=""),
    document_context: str = Form(default=""),
    components_json: str = Form(default="[]"),
    image_file: UploadFile = File(...),
    service: PatentLocalizationService = Depends(get_localization_service),
):
    try:
        _validate_image_upload(image_file)
        candidates = _parse_candidates(components_json)
        if not document_context.strip() and not candidates:
            raise PatentAnnotationError(
                "patent_document_context_missing",
                "请先解析专利说明书，再自动标注当前附图",
            )
        data = await _read_limited(image_file, IMAGE_MAX_BYTES, too_large_code="patent_image_too_large")
        if not data:
            raise PatentAnnotationError("patent_image_empty", "image file is empty")
        with tempfile.TemporaryDirectory(prefix="patent-page-") as temp_dir:
            work_dir = Path(temp_dir)
            image_path = work_dir / (image_file.filename or "page.png")
            image_path.write_bytes(data)
            return await service.localize(
                image_path,
                figure_no=figure_no,
                figure_description=figure_description,
                figure_context=figure_context,
                document_context=document_context[:24_000],
                candidates=candidates,
                work_dir=work_dir / "localization",
            )
    except (PatentAnnotationError, VisionModelError) as exc:
        raise _http_error(exc) from exc


def _validate_pdf_upload(upload: UploadFile) -> None:
    if not (upload.filename or "").lower().endswith(".pdf"):
        raise PatentAnnotationError("patent_pdf_invalid", "only PDF files are supported")


def _validate_image_upload(upload: UploadFile) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES or (upload.content_type or "").lower() not in IMAGE_TYPES:
        raise PatentAnnotationError("patent_image_invalid", "only PNG, JPG, JPEG, or WEBP images are supported")


async def _read_limited(upload: UploadFile, limit: int, *, too_large_code: str) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise PatentAnnotationError(too_large_code, "uploaded file is too large")
    return data


def _parse_candidates(value: str) -> list[LocalizationCandidate]:
    try:
        candidates = TypeAdapter(list[LocalizationCandidate]).validate_json(value)
    except ValidationError as exc:
        raise PatentAnnotationError("patent_components_invalid", "components_json is invalid") from exc
    if not candidates:
        return []
    return candidates


def _http_error(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "patent_annotation_failed")
    message = getattr(exc, "message", str(exc))
    status_code = 502
    if code in {
        "patent_pdf_invalid",
        "patent_pdf_empty",
        "patent_pdf_too_large",
        "patent_image_invalid",
        "patent_image_empty",
        "patent_image_too_large",
        "patent_components_invalid",
        "patent_document_context_missing",
        "patent_document_no_text",
    }:
        status_code = 422
    elif code == "vision_not_configured":
        status_code = 503
    elif code.startswith("vision_") or code.startswith("patent_image_"):
        status_code = 502
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
