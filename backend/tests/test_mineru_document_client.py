import io
import json
import zipfile

import httpx
import pytest

from app.core.mineru import MineruDocumentClient, MineruError


def _mineru_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sample/hybrid/sample.md", "# 说明书\n图中：1、壳体。")
        archive.writestr(
            "sample/hybrid/sample_content_list.json",
            json.dumps(
                [
                    {"page_idx": 0, "type": "text", "text": "说明书"},
                    {"page_idx": 1, "type": "text", "text": "图中：1、壳体。"},
                ],
                ensure_ascii=False,
            ),
        )
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_document_client_posts_mineru_v3_multipart_and_reads_zip(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        required_parts = [
            b'name="files"; filename="sample.pdf"',
            b'name="lang_list"',
            b"\r\nch\r\n",
            b'name="backend"',
            b"\r\nhybrid-auto-engine\r\n",
            b'name="parse_method"',
            b"\r\nauto\r\n",
            b'name="formula_enable"',
            b'name="table_enable"',
            b'name="image_analysis"',
            b'name="return_md"',
            b'name="return_content_list"',
            b'name="response_format_zip"',
            b"\r\ntrue\r\n",
        ]
        if request.url.path != "/file_parse" or not all(part in body for part in required_parts):
            return httpx.Response(422, json={"detail": "invalid multipart request"})
        return httpx.Response(200, content=_mineru_zip(), headers={"content-type": "application/zip"})

    client = MineruDocumentClient(
        api_url="http://mineru.test",
        endpoint="file_parse",
        backend="hybrid-auto-engine",
        ocr_lang="ch",
        result_mode="zip",
        enable_table=True,
        enable_formula=True,
        enable_image_analysis=True,
        enable_ocr=True,
        timeout=60,
        transport=httpx.MockTransport(handler),
    )

    payload = await client.fetch_payload(pdf_path)

    assert payload["markdown"] == "# 说明书\n图中：1、壳体。"
    assert payload["content_list"] == [
        {"page_idx": 0, "type": "text", "text": "说明书"},
        {"page_idx": 1, "type": "text", "text": "图中：1、壳体。"},
    ]


@pytest.mark.asyncio
async def test_document_client_normalizes_mineru_json_results(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "backend": "hybrid-auto-engine",
                "results": {
                    "sample": {
                        "md_content": "# 说明书",
                        "content_list": [{"page_idx": 0, "type": "text", "text": "说明书"}],
                    }
                },
            },
        )

    client = MineruDocumentClient(
        api_url="http://mineru.test/",
        endpoint="/file_parse",
        result_mode="json_base64",
        transport=httpx.MockTransport(handler),
    )

    payload = await client.fetch_payload(pdf_path)

    assert payload == {
        "markdown": "# 说明书",
        "content_list": [{"page_idx": 0, "type": "text", "text": "说明书"}],
    }


@pytest.mark.asyncio
async def test_document_client_maps_http_failure_to_stable_error(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "busy"})

    client = MineruDocumentClient(
        api_url="http://mineru.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MineruError) as error:
        await client.fetch_payload(pdf_path)

    assert error.value.code == "mineru_connection_failed"
