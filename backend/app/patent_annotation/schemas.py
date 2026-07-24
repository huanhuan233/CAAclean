from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PatentDocumentPage(BaseModel):
    page_no: int = Field(ge=1)
    text: str
    markdown: str | None = None
    image_refs: list[str] = Field(default_factory=list)
    parser: Literal["mineru", "pypdf"]


class PatentDocumentContent(BaseModel):
    pages: list[PatentDocumentPage] = Field(default_factory=list)
    full_text: str
    parser: Literal["mineru", "pypdf"]
    warnings: list[str] = Field(default_factory=list)


class PatentComponent(BaseModel):
    ref_no: str
    name: str


class PatentDetailMarker(BaseModel):
    marker: str
    parent_figure_no: str


class PatentFigure(BaseModel):
    figure_no: str
    description: str = ""
    context: str = ""
    explicit_ref_nos: list[str] = Field(default_factory=list)
    candidate_ref_nos: list[str] = Field(default_factory=list)
    detail_markers: list[PatentDetailMarker] = Field(default_factory=list)


class PatentDocumentParseResult(BaseModel):
    file_name: str
    parser: Literal["mineru", "pypdf"]
    components: list[PatentComponent] = Field(default_factory=list)
    figures: list[PatentFigure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelLocalizationPoint(BaseModel):
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)


class ModelLocalizationBox(BaseModel):
    x_min: float = Field(ge=0, le=1000)
    y_min: float = Field(ge=0, le=1000)
    x_max: float = Field(ge=0, le=1000)
    y_max: float = Field(ge=0, le=1000)


class ModelLocalizationItem(BaseModel):
    ref_no: str
    visible: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = ""
    anchor: ModelLocalizationPoint | None = None
    bbox: ModelLocalizationBox | None = None


class ModelLocalizationOutput(BaseModel):
    items: list[ModelLocalizationItem] = Field(default_factory=list)


class NormalizedPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class NormalizedBox(BaseModel):
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)


class NormalizedLocalizationItem(BaseModel):
    ref_no: str
    visible: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = ""
    anchor: NormalizedPoint | None = None
    bbox: NormalizedBox | None = None
    review_state: Literal["accepted", "review", "rejected"]


class NormalizedLocalizationResult(BaseModel):
    items: list[NormalizedLocalizationItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LocalizationCandidate(BaseModel):
    ref_no: str
    name: str


RawModelPoint = ModelLocalizationPoint
RawModelBox = ModelLocalizationBox
RawModelItem = ModelLocalizationItem
RawModelOutput = ModelLocalizationOutput
NormalizedLocalizationPoint = NormalizedPoint
NormalizedLocalizationBox = NormalizedBox
LocalizationResult = NormalizedLocalizationResult
