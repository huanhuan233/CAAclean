import io

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings, get_settings
from app.main import app
from app.patent_annotation.router import get_document_parser, get_localization_service
from app.patent_annotation.schemas import (
    NormalizedLocalizationItem,
    NormalizedLocalizationResult,
    NormalizedPoint,
    PatentComponent,
    PatentDocumentParseResult,
)


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeParser:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def parse(self, pdf_path, *, file_name, fast=False):
        self.calls.append({"pdf_path": pdf_path, "file_name": file_name, "fast": fast})
        if self.error:
            raise self.error
        return self.result


class FakeLocalizationService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def localize(self, image_path, *, figure_no, figure_description, figure_context, candidates, work_dir):
        self.calls.append(
            {
                "image_path": image_path,
                "figure_no": figure_no,
                "figure_description": figure_description,
                "figure_context": figure_context,
                "candidates": candidates,
                "work_dir": work_dir,
            }
        )
        if self.error:
            raise self.error
        return self.result


def client_with(overrides):
    app.dependency_overrides.update(overrides)
    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.pop(get_document_parser, None)
    app.dependency_overrides.pop(get_localization_service, None)
    app.dependency_overrides.pop(get_settings, None)


def test_parse_document_rejects_non_pdf():
    client = client_with({get_document_parser: lambda: FakeParser()})
    try:
        response = client.post(
            "/api/patent-annotations/parse-document",
            files={"pdf_file": ("sample.txt", b"hello", "text/plain")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "patent_pdf_invalid"


def test_parse_document_rejects_empty_and_oversized_pdf():
    client = client_with({get_document_parser: lambda: FakeParser()})
    try:
        empty = client.post(
            "/api/patent-annotations/parse-document",
            files={"pdf_file": ("sample.pdf", b"", "application/pdf")},
        )
        oversized = client.post(
            "/api/patent-annotations/parse-document",
            files={"pdf_file": ("sample.pdf", b"x" * (30 * 1024 * 1024 + 1), "application/pdf")},
        )
    finally:
        clear_overrides()

    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "patent_pdf_empty"
    assert oversized.status_code == 422
    assert oversized.json()["detail"]["code"] == "patent_pdf_too_large"


def test_parse_document_returns_parser_response_and_fast_flag():
    parser = FakeParser(
        PatentDocumentParseResult(
            file_name="sample.pdf",
            parser="pypdf",
            components=[PatentComponent(ref_no="1", name="shell")],
            figures=[],
            warnings=[],
        )
    )
    client = client_with({get_document_parser: lambda: parser})
    try:
        response = client.post(
            "/api/patent-annotations/parse-document",
            data={"fast": "true"},
            files={"pdf_file": ("sample.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["components"][0]["ref_no"] == "1"
    assert parser.calls[0]["fast"] is True


def test_localize_page_rejects_bad_components_json():
    client = client_with({get_localization_service: lambda: FakeLocalizationService()})
    try:
        response = client.post(
            "/api/patent-annotations/localize-page",
            data={"figure_no": "1", "components_json": "[]"},
            files={"image_file": ("page.png", png_bytes(), "image/png")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "patent_components_invalid"


def test_localize_page_rejects_non_image():
    client = client_with({get_localization_service: lambda: FakeLocalizationService()})
    try:
        response = client.post(
            "/api/patent-annotations/localize-page",
            data={"figure_no": "1", "components_json": '[{"ref_no":"1","name":"shell"}]'},
            files={"image_file": ("page.txt", b"hello", "text/plain")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "patent_image_invalid"


def test_localize_page_missing_vision_configuration_returns_503():
    app.dependency_overrides[get_settings] = lambda: Settings(
        vision_model="",
        vision_binding_host="",
        vision_binding_api_key="",
    )
    client = TestClient(app)
    try:
        response = client.post(
            "/api/patent-annotations/localize-page",
            data={"figure_no": "1", "components_json": '[{"ref_no":"1","name":"shell"}]'},
            files={"image_file": ("page.png", png_bytes(), "image/png")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "vision_not_configured"


def test_localize_page_returns_fake_localization_response():
    service = FakeLocalizationService(
        NormalizedLocalizationResult(
            items=[
                NormalizedLocalizationItem(
                    ref_no="1",
                    visible=True,
                    confidence=0.9,
                    anchor=NormalizedPoint(x=0.25, y=0.75),
                    review_state="accepted",
                )
            ],
            warnings=[],
        )
    )
    client = client_with({get_localization_service: lambda: service})
    try:
        response = client.post(
            "/api/patent-annotations/localize-page",
            data={
                "figure_no": "4",
                "figure_description": "detail",
                "figure_context": "shell 1",
                "components_json": '[{"ref_no":"1","name":"shell"}]',
            },
            files={"image_file": ("page.png", png_bytes(), "image/png")},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["anchor"]["x"] == 0.25
    assert service.calls[0]["figure_no"] == "4"
