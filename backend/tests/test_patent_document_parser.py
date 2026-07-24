from app.patent_annotation.document_parser import parse_patent_structure
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


def test_parse_patent_structure_extracts_legend_figures_and_detail_marker():
    """Removing legend/figure/detail parsing must make this test fail."""
    result = parse_patent_structure(make_content(PATENT_TEXT), file_name="sample.pdf")

    assert [item.ref_no for item in result.components] == ["1", "2", "61", "68"]
    assert [item.figure_no for item in result.figures] == ["1", "2", "4"]
    assert result.figures[-1].explicit_ref_nos == ["68"]
    assert result.figures[-1].detail_markers[0].marker == "A"
    assert result.figures[-1].detail_markers[0].parent_figure_no == "3"


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
