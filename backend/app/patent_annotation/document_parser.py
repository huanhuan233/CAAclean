from __future__ import annotations

import re

from app.patent_annotation.schemas import (
    PatentComponent,
    PatentDetailMarker,
    PatentDocumentContent,
    PatentDocumentParseResult,
    PatentFigure,
)


SECTION_HEADING_RE = re.compile(r"(?:具体实施方式|实施例|权利要求书?|发明内容|摘要)")
FIGURE_SECTION_END_RE = re.compile(r"(?:图\s*中\s*[:：]|具体实施方式|实施例|权利要求书?|发明内容|摘要)")
LEGEND_ENTRY_RE = re.compile(
    r"(?P<ref>[A-Za-z]|\d+[A-Za-z]?)\s*(?:、|,|，|\.|．|:|：)\s*"
    r"(?P<name>[\u4e00-\u9fffA-Za-z][^；;。]*?)\s*(?=；|;|。|$)"
)
PARENTHETICAL_ENTRY_RE = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9 _-]{0,40}?)\s*"
    r"[（(]\s*(?P<ref>[A-Za-z]|\d+[A-Za-z]?)\s*[）)]"
)
FIGURE_RE = re.compile(r"图\s*(?P<figure_no>\d+)\s*(?:为|是|示|表示|显示|[:：])\s*(?P<description>[^。；;\n]*)")
DETAIL_MARKER_RE = re.compile(r"图\s*(?P<parent>\d+)\s*中\s*(?P<marker>[A-Za-z])\s*处\s*放大")


def normalize_match_text(text: str) -> str:
    """Normalize only the syntax needed by deterministic text matching."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("（", "(").replace("）", ")")
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[\u4e00-\u9fff])", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _before_body(text: str) -> str:
    match = SECTION_HEADING_RE.search(text)
    return text[: match.start()] if match else text


def _append_component(components: list[PatentComponent], ref_no: str, name: str) -> None:
    if any(component.ref_no == ref_no for component in components):
        return
    cleaned_name = name.strip(" ，,、:：.．")
    if cleaned_name:
        components.append(PatentComponent(ref_no=ref_no, name=cleaned_name))


def extract_components(text: str) -> list[PatentComponent]:
    """Extract ordered reference-number legend entries before claim/body sections."""
    pre_body = _before_body(normalize_match_text(text))
    components: list[PatentComponent] = []
    legend_match = re.search(r"图\s*中\s*[:：]", pre_body)
    if legend_match:
        legend_text = pre_body[legend_match.end() :]
        for match in LEGEND_ENTRY_RE.finditer(legend_text):
            _append_component(components, match.group("ref"), match.group("name"))

    for match in PARENTHETICAL_ENTRY_RE.finditer(pre_body):
        _append_component(components, match.group("ref"), match.group("name"))
    return components


def _figure_section(text: str) -> str:
    normalized = normalize_match_text(text)
    start = re.search(r"附\s*图\s*说\s*明\s*[:：]?", normalized)
    if not start:
        return ""
    section = normalized[start.end() :]
    end = FIGURE_SECTION_END_RE.search(section)
    return section[: end.start()] if end else section


def _figure_context(text: str, figure_no: str) -> str:
    paragraphs = re.split(r"(?:\n\s*\n|\n|(?<=[。！？!?]))", text)
    figure_re = re.compile(rf"图\s*{re.escape(figure_no)}(?:\D|$)")
    matches = [paragraph.strip() for paragraph in paragraphs if figure_re.search(paragraph)]
    return "\n".join(matches)[:4000]


def _explicit_ref_nos(context: str, components: list[PatentComponent]) -> list[str]:
    explicit: list[str] = []
    for component in components:
        ref_no = re.escape(component.ref_no)
        name = re.escape(component.name)
        patterns = (
            rf"{name}\s*(?:[（(]\s*)?{ref_no}(?:\s*[）)])?",
            rf"{ref_no}\s*(?:号\s*)?{name}",
        )
        if any(re.search(pattern, context) for pattern in patterns):
            explicit.append(component.ref_no)
    return explicit


def extract_figures(text: str, components: list[PatentComponent]) -> list[PatentFigure]:
    """Extract described figures with capped context and deterministic candidates."""
    figures: list[PatentFigure] = []
    source_text = text.replace("\r\n", "\n").replace("\r", "\n")
    for match in FIGURE_RE.finditer(_figure_section(source_text)):
        figure_no = match.group("figure_no")
        if any(figure.figure_no == figure_no for figure in figures):
            continue
        description = match.group("description").strip()
        detail_markers = [
            PatentDetailMarker(marker=detail.group("marker"), parent_figure_no=detail.group("parent"))
            for detail in DETAIL_MARKER_RE.finditer(description)
        ]
        context = _figure_context(source_text, figure_no)
        explicit_ref_nos = _explicit_ref_nos(context, components)
        candidate_ref_nos = explicit_ref_nos + [
            component.ref_no for component in components if component.ref_no not in explicit_ref_nos
        ]
        figures.append(
            PatentFigure(
                figure_no=figure_no,
                description=description,
                context=context,
                explicit_ref_nos=explicit_ref_nos,
                candidate_ref_nos=candidate_ref_nos,
                detail_markers=detail_markers,
            )
        )
    return figures


def parse_patent_structure(content: PatentDocumentContent, file_name: str) -> PatentDocumentParseResult:
    """Build the parser-independent patent structure used by later API layers."""
    text = content.full_text or "\n".join(page.text for page in content.pages)
    components = extract_components(text)
    return PatentDocumentParseResult(
        file_name=file_name,
        parser=content.parser,
        components=components,
        figures=extract_figures(text, components),
        warnings=content.warnings,
    )
