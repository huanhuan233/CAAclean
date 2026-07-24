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
