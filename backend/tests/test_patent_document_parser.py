import pytest

from app.core.mineru import MineruError
from app.patent_annotation.document_parser import (
    PatentDocumentParser,
    build_patent_document_context,
    mineru_payload_to_content,
    parse_patent_structure,
)
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.schemas import PatentDocumentContent, PatentDocumentPage


PATENT_TEXT = """附图说明
图1为本发明装置的整体结构示意图。
图2为盖板的结构示意图。
图4为图3中A处放大的局部结构示意图。
图中：1、壳体；2、盖板；61、导向件；68、弹簧。

具体实施方式
如图4所示，弹簧68安装在壳体内。
权利要求1：一种装置，包括第99连接部。
"""


def make_content(*pages: str) -> PatentDocumentContent:
    return PatentDocumentContent(
        pages=[
            PatentDocumentPage(page_no=index, text=text, parser="pypdf")
            for index, text in enumerate(pages, start=1)
        ],
        full_text="\n".join(pages),
        parser="pypdf",
    )


class FakeMineru:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def fetch_payload(self, path):
        self.calls += 1
        return self.payload


class FailingMineru:
    def __init__(self, code="mineru_timeout"):
        self.code = code
        self.calls = 0

    async def fetch_payload(self, path):
        self.calls += 1
        raise MineruError(self.code, self.code)


def make_text_pdf(tmp_path, text="selectable patent text"):
    path = tmp_path / "sample.pdf"
    encoded = text.encode("ascii")
    stream = b"BT /F1 12 Tf 72 720 Td (" + encoded + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(str(index).encode("ascii") + b" 0 obj\n" + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(b"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n")
    chunks.append(str(xref_offset).encode("ascii") + b"\n%%EOF\n")
    path.write_bytes(b"".join(chunks))
    return path


def make_partial_text_pdf(tmp_path):
    path = tmp_path / "partial.pdf"
    stream = b"BT /F1 12 Tf 72 720 Td (selectable text) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(str(index).encode("ascii") + b" 0 obj\n" + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(b"xref\n0 7\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(b"trailer << /Root 1 0 R /Size 7 >>\nstartxref\n")
    chunks.append(str(xref_offset).encode("ascii") + b"\n%%EOF\n")
    path.write_bytes(b"".join(chunks))
    return path


def make_blank_pdf(tmp_path):
    path = tmp_path / "blank.pdf"
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n186\n%%EOF\n"
    )
    return path


def test_parse_patent_structure_extracts_legend_figures_and_detail_marker():
    """Removing legend/figure/detail parsing must make this test fail."""
    result = parse_patent_structure(make_content(PATENT_TEXT), file_name="sample.pdf")

    assert [item.ref_no for item in result.components] == ["1", "2", "61", "68"]
    assert [item.figure_no for item in result.figures] == ["1", "2", "4"]
    assert result.figures[-1].explicit_ref_nos == ["68"]
    assert result.figures[-1].detail_markers[0].marker == "A"
    assert result.figures[-1].detail_markers[0].parent_figure_no == "3"
    assert "A" not in [item.ref_no for item in result.components]


def test_parenthetical_component_entries_only_fill_legend_gaps():
    """Removing the parenthetical fallback must make this test fail."""
    text = """附图说明
图1为结构示意图。
图中：1、壳体。
壳体（1）、盖板(2)、导向件（61）、弹簧（68）。
具体实施方式
"""

    result = parse_patent_structure(make_content(text), file_name="sample.pdf")

    assert [(item.ref_no, item.name) for item in result.components] == [
        ("1", "壳体"),
        ("2", "盖板"),
        ("61", "导向件"),
        ("68", "弹簧"),
    ]


def test_cross_page_legend_and_figure_sections_are_combined():
    """Ignoring adjacent pages must make this test fail."""
    result = parse_patent_structure(
        make_content("附图说明\n图1为整体结构示意图。", "图中：1、壳体；2、盖板。"),
        file_name="sample.pdf",
    )

    assert [item.figure_no for item in result.figures] == ["1"]
    assert [item.ref_no for item in result.components] == ["1", "2"]


def test_document_context_preserves_page_boundaries_for_vision_model():
    content = make_content("标题\n附图说明\n图1为结构示意图。", "具体实施方式\n如图1所示，壳体1连接盖板2。")

    context, warnings = build_patent_document_context(content)

    assert "[PAGE 1]" in context
    assert "[PAGE 2]" in context
    assert "如图1所示，壳体1连接盖板2。" in context
    assert warnings == []


def test_long_document_context_prioritizes_patent_figure_evidence_and_warns():
    content = make_content(
        "标题\n" + ("普通背景内容\n" * 100) + "附图说明\n图1为整体结构示意图。",
        ("无关描述\n" * 100) + "具体实施方式\n请参阅图1，壳体1连接盖板2。",
    )

    context, warnings = build_patent_document_context(content, max_chars=180)

    assert len(context) <= 180
    assert "图1" in context
    assert warnings == ["patent_document_context_truncated"]


def test_figure_candidates_put_explicit_references_before_component_order():
    """Dropping explicit-reference priority must make this test fail."""
    result = parse_patent_structure(make_content(PATENT_TEXT), file_name="sample.pdf")

    assert result.figures[-1].candidate_ref_nos == ["68", "1", "2", "61"]


def test_claim_sequence_numbers_do_not_become_components():
    """Parsing claim numbers as legend entries must make this test fail."""
    text = """附图说明
图1为结构示意图。
图中：1、壳体。
具体实施方式
权利要求1：壳体包括99个孔和第100连接部。
"""

    result = parse_patent_structure(make_content(text), file_name="sample.pdf")

    assert [item.ref_no for item in result.components] == ["1"]


def test_complete_patent_order_finds_multiline_legend_after_prior_sections():
    """Stopping at a heading before the legend must make this test fail."""
    text = """摘要
本装置涉及一种驱动臂（1）。
权利要求书
1.一种装置，包括驱动臂（1）和顶部活动连接有曲轴一（2）的支架。
说明书
技术领域
本发明涉及机械设备领域。
发明内容
本发明提供一种传动装置。
附图说明
图1为装置主视图
图2为装置侧视图
图4为图3中A处放大的局部视图
图中：1、驱动臂；2、曲轴一；3、伸缩筒；4、曲轴二；5、丝杆；61、
旋转槽口；62、连接轴；63、限位块；64、轴套；65、压板；66、螺母；67、导向杆；68、弹簧。
具体实施方式
如图4所示，弹簧68设置于旋转槽口61内。
"""

    result = parse_patent_structure(make_content(text), file_name="complete.pdf")

    assert [(item.ref_no, item.name) for item in result.components] == [
        ("1", "驱动臂"),
        ("2", "曲轴一"),
        ("3", "伸缩筒"),
        ("4", "曲轴二"),
        ("5", "丝杆"),
        ("61", "旋转槽口"),
        ("62", "连接轴"),
        ("63", "限位块"),
        ("64", "轴套"),
        ("65", "压板"),
        ("66", "螺母"),
        ("67", "导向杆"),
        ("68", "弹簧"),
    ]
    assert "A" not in [item.ref_no for item in result.components]


def test_parenthetical_fallback_does_not_scan_claim_body_without_a_naming_section():
    """Scanning arbitrary claims for parenthetical refs must make this test fail."""
    text = """摘要
一种传动装置。
权利要求书
1.一种装置，包括驱动臂（1）以及与驱动臂连接的曲轴一（2）。
说明书
具体实施方式
驱动臂用于传递动力。
"""

    result = parse_patent_structure(make_content(text), file_name="claims.pdf")

    assert result.components == []


def test_abstract_figure_legend_does_not_preempt_drawing_section_legend():
    """Searching the whole document for the first 图中 legend must make this test fail."""
    text = """摘要
示意图中：9、摘要区域。
说明书
附图说明
图1为结构示意图。
图中：1、壳体；2、盖板。
具体实施方式
"""

    result = parse_patent_structure(make_content(text), file_name="legend.pdf")

    assert [(item.ref_no, item.name) for item in result.components] == [("1", "壳体"), ("2", "盖板")]


def test_inline_component_name_phrase_is_not_a_naming_section():
    """Treating inline 部件名称 text as a heading must make this test fail."""
    text = """摘要
本摘要说明部件名称包括壳体（1）和盖板（2）。
说明书
具体实施方式
壳体用于安装盖板。
"""

    result = parse_patent_structure(make_content(text), file_name="inline.pdf")

    assert result.components == []


def test_detail_marker_identifier_is_not_returned_as_a_component():
    """Keeping an identified detail marker in components must make this test fail."""
    text = """附图说明
图2为图1中A处放大的局部视图。
图中：A、放大区域；1、壳体。
具体实施方式
"""

    result = parse_patent_structure(make_content(text), file_name="detail.pdf")

    assert [item.ref_no for item in result.components] == ["1"]


def test_line_delimited_figure_descriptions_keep_boundaries_and_original_parentheses():
    """Collapsing figure-entry newlines must make this test fail."""
    text = """附图说明
图1为整体结构示意图（主视图）
图2为局部结构示意图（侧视图）
图中：1、壳体。
具体实施方式
"""

    result = parse_patent_structure(make_content(text), file_name="figures.pdf")

    assert [figure.description for figure in result.figures] == [
        "整体结构示意图（主视图）",
        "局部结构示意图（侧视图）",
    ]


def test_explicit_reference_matching_does_not_match_number_prefixes():
    """Treating ref 1 as explicit in ref 10 must make this test fail."""
    text = """附图说明
图1为壳体结构示意图。
图中：1、壳体；10、壳体。
具体实施方式
如图1所示，壳体10设置在底座上。
"""

    result = parse_patent_structure(make_content(text), file_name="overlap.pdf")

    assert result.figures[0].explicit_ref_nos == ["10"]


@pytest.mark.asyncio
async def test_mineru_success_reports_parser(tmp_path):
    parser = PatentDocumentParser(mineru_client=FakeMineru({"pages": [{"page_no": 1, "text": PATENT_TEXT}]}))

    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf")

    assert result.parser == "mineru"
    assert [item.ref_no for item in result.components] == ["1", "2", "61", "68"]


@pytest.mark.asyncio
async def test_mineru_timeout_falls_back_to_pypdf(tmp_path):
    parser = PatentDocumentParser(mineru_client=FailingMineru("mineru_timeout"))

    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf")

    assert result.parser == "pypdf"
    assert "mineru_timeout" in result.warnings


@pytest.mark.asyncio
async def test_fast_mode_skips_mineru(tmp_path):
    mineru = FakeMineru({"pages": [{"page_no": 1, "text": PATENT_TEXT}]})
    parser = PatentDocumentParser(mineru_client=mineru)

    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf", fast=True)

    assert result.parser == "pypdf"
    assert mineru.calls == 0


def test_mineru_payload_normalization_accepts_nested_shapes():
    content = mineru_payload_to_content(
        {
            "result": {
                "content_list": [
                    {"page_idx": 0, "text": "page one", "img_path": "p1.png"},
                    {"page": 2, "type": "text", "content": "page two", "image_refs": ["p2.png"]},
                ],
                "markdown": "# title\nbody",
            }
        }
    )

    assert content.parser == "mineru"
    assert content.full_text == "page one\npage two\n# title\nbody"
    assert [page.page_no for page in content.pages] == [1, 2]
    assert content.pages[0].image_refs == ["p1.png"]
    assert content.pages[1].image_refs == ["p2.png"]


def test_mineru_payload_prefers_populated_result_when_data_is_empty():
    content = mineru_payload_to_content({"data": {}, "result": {"text": "usable text"}})

    assert content.full_text == "usable text"


def test_mineru_content_list_groups_same_page_blocks():
    content = mineru_payload_to_content(
        {
            "pages": [],
            "content_list": [
                {"page_idx": 0, "text": "first", "img_path": "a.png"},
                {"page_idx": 0, "text": "second", "img_path": "b.png"},
                {"page_idx": 1, "text": "third"},
            ],
        }
    )

    assert [(page.page_no, page.text, page.image_refs) for page in content.pages] == [
        (1, "first\nsecond", ["a.png", "b.png"]),
        (2, "third", []),
    ]


def test_mineru_markdown_only_payload_preserves_page_markdown():
    content = mineru_payload_to_content({"markdown": "# title"})

    assert content.pages[0].markdown == "# title"


@pytest.mark.asyncio
async def test_empty_mineru_payload_falls_back_to_text_pdf(tmp_path):
    parser = PatentDocumentParser(mineru_client=FakeMineru({"pages": [{"page_no": 1, "text": "   "}]}))

    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf")

    assert result.parser == "pypdf"
    assert "mineru_no_text" in result.warnings


@pytest.mark.asyncio
async def test_pypdf_partial_empty_pages_are_reported(tmp_path):
    result = await PatentDocumentParser(mineru_client=FailingMineru()).parse(
        make_partial_text_pdf(tmp_path),
        file_name="partial.pdf",
    )

    assert result.parser == "pypdf"
    assert "pypdf_page_1_no_text" in result.warnings


@pytest.mark.asyncio
async def test_malformed_pdf_raises_parse_failed(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")

    with pytest.raises(PatentAnnotationError) as exc:
        await PatentDocumentParser(mineru_client=FailingMineru()).parse(path, file_name="bad.pdf")

    assert exc.value.code == "patent_document_parse_failed"


@pytest.mark.asyncio
async def test_encrypted_pdf_raises_parse_failed(tmp_path):
    from pypdf import PdfWriter

    path = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    with path.open("wb") as handle:
        writer.write(handle)

    with pytest.raises(PatentAnnotationError) as exc:
        await PatentDocumentParser(mineru_client=FailingMineru()).parse(path, file_name="encrypted.pdf")

    assert exc.value.code == "patent_document_parse_failed"


@pytest.mark.asyncio
async def test_both_parsers_empty_raise_no_text(tmp_path):
    parser = PatentDocumentParser(mineru_client=FakeMineru({"pages": [{"page_no": 1, "text": ""}]}))

    with pytest.raises(PatentAnnotationError) as exc:
        await parser.parse(make_blank_pdf(tmp_path), file_name="blank.pdf")

    assert exc.value.code == "patent_document_no_text"
