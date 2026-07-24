from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.mineru import MineruClient, MineruError
from app.patent_annotation.errors import PatentAnnotationError
from app.patent_annotation.schemas import (
    PatentComponent,
    PatentDetailMarker,
    PatentDocumentPage,
    PatentDocumentContent,
    PatentDocumentParseResult,
    PatentFigure,
)


SECTION_HEADING_RE = re.compile(r"(?:具体实施方式|实施例|权利要求书?|发明内容|摘要|背景技术|技术领域)")
DRAWING_SECTION_RE = re.compile(r"附\s*图\s*说\s*明\s*[:：]?")
COMPONENT_NAMING_SECTION_RE = re.compile(
    r"(?:^|[\n\r。；;])\s*(?:附图标记说明|附图标记|标号说明|部件名称说明|部件名称)\s*(?:[:：]|\n|$)",
    re.MULTILINE,
)
FIGURE_SECTION_END_RE = re.compile(r"(?:图\s*中\s*[:：]|具体实施方式|实施例|权利要求书?|发明内容|摘要)")
LEGEND_ENTRY_RE = re.compile(
    r"(?P<ref>[A-Za-z]|\d+[A-Za-z]?)\s*(?:、|,|，|\.|．|:|：)\s*"
    r"(?P<name>[\u4e00-\u9fffA-Za-z][^；;。]*?)\s*(?=；|;|。|$)"
)
PARENTHETICAL_ENTRY_RE = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9 _-]{0,40}?)\s*"
    r"[（(]\s*(?P<ref>[A-Za-z]|\d+[A-Za-z]?)\s*[）)]"
)
FIGURE_ENTRY_PREFIX = r"图\s*\d+\s*(?:为|是|示|表示|显示|[:：])"
FIGURE_RE = re.compile(
    rf"图\s*(?P<figure_no>\d+)\s*(?:为|是|示|表示|显示|[:：])\s*"
    rf"(?P<description>.*?)(?=\s*{FIGURE_ENTRY_PREFIX}|[。；;]|$)",
    re.DOTALL,
)
DETAIL_MARKER_RE = re.compile(r"图\s*(?P<parent>\d+)\s*中\s*(?P<marker>[A-Za-z])\s*处\s*放大")


def normalize_match_text(text: str) -> str:
    """Normalize only the syntax needed by deterministic text matching."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("（", "(").replace("）", ")")
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[\u4e00-\u9fff])", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _unwrap_mineru_payload(payload: dict[str, Any]) -> dict[str, Any]:
    current: dict[str, Any] = payload
    while True:
        for key in ("data", "result"):
            nested = current.get(key)
            if isinstance(nested, dict):
                current = nested
                break
        else:
            return current


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_image_refs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("image_refs", "images"):
        value = item.get(key)
        if isinstance(value, list):
            refs.extend(str(ref) for ref in value if ref)
    for key in ("img_path", "image_path"):
        value = item.get(key)
        if value:
            refs.append(str(value))
    return refs


def _page_no(item: dict[str, Any], fallback: int) -> int:
    for key in ("page_no", "page"):
        value = item.get(key)
        if isinstance(value, int) and value >= 1:
            return value
    page_idx = item.get("page_idx")
    if isinstance(page_idx, int) and page_idx >= 0:
        return page_idx + 1
    return fallback


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        part
        for part in (
            _as_text(item.get("text")),
            _as_text(item.get("content")),
            _as_text(item.get("markdown")),
        )
        if part.strip()
    )


def mineru_payload_to_content(payload: dict[str, Any]) -> PatentDocumentContent:
    """Normalize common MinerU payload shapes to the public patent text schema."""
    if not isinstance(payload, dict):
        raise PatentAnnotationError("mineru_invalid_result", "MinerU returned an invalid result")
    data = _unwrap_mineru_payload(payload)
    pages: list[PatentDocumentPage] = []
    fragments: list[str] = []

    source_items = data.get("pages")
    if not isinstance(source_items, list):
        source_items = data.get("content_list")
    if isinstance(source_items, list):
        for index, raw_item in enumerate(source_items, start=1):
            if not isinstance(raw_item, dict):
                continue
            text = _item_text(raw_item)
            if text.strip():
                fragments.append(text)
            pages.append(
                PatentDocumentPage(
                    page_no=_page_no(raw_item, index),
                    text=text,
                    markdown=_as_text(raw_item.get("markdown")) or None,
                    image_refs=_as_image_refs(raw_item),
                    parser="mineru",
                )
            )

    canonical_full_text = _as_text(data.get("full_text"))
    if canonical_full_text.strip():
        full_text = canonical_full_text
    else:
        for key in ("text", "markdown"):
            text = _as_text(data.get(key))
            if text.strip():
                fragments.append(text)
        full_text = "\n".join(fragment for fragment in fragments if fragment.strip())
    if not full_text.strip():
        raise PatentAnnotationError("mineru_no_text", "MinerU returned no usable text")
    if not pages:
        pages.append(PatentDocumentPage(page_no=1, text=full_text, parser="mineru"))
    return PatentDocumentContent(pages=pages, full_text=full_text, parser="mineru")


def _component_scope(text: str) -> tuple[str, bool]:
    """Return a bounded component-naming scope and whether it is a 图中 legend."""
    normalized = normalize_match_text(text)
    drawing_match = DRAWING_SECTION_RE.search(text)
    legend_source = normalize_match_text(text[drawing_match.end() :]) if drawing_match else normalized
    legend_match = re.search(r"图\s*中\s*[:：]", legend_source)
    if legend_match:
        scope = legend_source[legend_match.end() :]
        end = SECTION_HEADING_RE.search(scope)
        return (scope[: end.start()] if end else scope), True

    naming_match = COMPONENT_NAMING_SECTION_RE.search(text)
    if not naming_match:
        return "", False
    scope = normalize_match_text(text[naming_match.end() :])
    end = SECTION_HEADING_RE.search(scope)
    return (scope[: end.start()] if end else scope), False


def _append_component(components: list[PatentComponent], ref_no: str, name: str) -> None:
    if any(component.ref_no == ref_no for component in components):
        return
    cleaned_name = name.strip(" ，,、:：.．")
    if cleaned_name:
        components.append(PatentComponent(ref_no=ref_no, name=cleaned_name))


def extract_components(text: str) -> list[PatentComponent]:
    """Extract ordered reference-number legend entries before claim/body sections."""
    scope, has_legend = _component_scope(text)
    components: list[PatentComponent] = []
    if has_legend:
        for match in LEGEND_ENTRY_RE.finditer(scope):
            _append_component(components, match.group("ref"), match.group("name"))

    for match in PARENTHETICAL_ENTRY_RE.finditer(scope):
        _append_component(components, match.group("ref"), match.group("name"))
    detail_markers = {match.group("marker") for match in DETAIL_MARKER_RE.finditer(normalize_match_text(text))}
    return [component for component in components if component.ref_no not in detail_markers]


def _figure_section(text: str) -> str:
    start = re.search(r"附\s*图\s*说\s*明\s*[:：]?", text)
    if not start:
        return ""
    section = text[start.end() :]
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
            rf"{name}\s*(?:[（(]\s*)?{ref_no}(?![A-Za-z0-9])(?:\s*[）)])?",
            rf"(?<![A-Za-z0-9]){ref_no}(?![A-Za-z0-9])\s*(?:号\s*)?{name}",
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
        description = re.sub(r"\s+", " ", match.group("description")).strip()
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


def _pypdf_to_content(pdf_path: Path) -> PatentDocumentContent:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PatentAnnotationError("patent_document_parse_failed", "pypdf is not installed") from exc

    warnings: list[str] = []
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            decrypt_result = reader.decrypt("")
            if decrypt_result == 0:
                raise PatentAnnotationError("patent_document_parse_failed", "PDF is encrypted")
        pages: list[PatentDocumentPage] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                warnings.append(f"pypdf_page_{index}_no_text")
            pages.append(PatentDocumentPage(page_no=index, text=text, parser="pypdf"))
    except PatentAnnotationError:
        raise
    except Exception as exc:
        raise PatentAnnotationError("patent_document_parse_failed", "PDF text extraction failed") from exc

    full_text = "\n".join(page.text for page in pages)
    return PatentDocumentContent(pages=pages, full_text=full_text, parser="pypdf", warnings=warnings)


class PatentDocumentParser:
    """Parse a patent PDF into deterministic figure/component structure."""

    def __init__(self, mineru_client: MineruClient | None = None):
        self.mineru_client = mineru_client or MineruClient()

    async def parse(self, pdf_path: Path, *, file_name: str, fast: bool = False) -> PatentDocumentParseResult:
        warnings: list[str] = []
        if not fast:
            try:
                payload = await self.mineru_client.fetch_payload(Path(pdf_path))
                content = mineru_payload_to_content(payload)
                return parse_patent_structure(content, file_name=file_name)
            except MineruError as exc:
                warnings.append(exc.code)
            except PatentAnnotationError as exc:
                if exc.code not in {"mineru_invalid_result", "mineru_no_text"}:
                    raise
                warnings.append(exc.code)

        content = _pypdf_to_content(Path(pdf_path))
        content.warnings[:] = [*warnings, *content.warnings]
        if not content.full_text.strip():
            raise PatentAnnotationError(
                "patent_document_no_text",
                "当前版本仅支持带文字层或 MinerU 可识别的 PDF",
            )
        return parse_patent_structure(content, file_name=file_name)
