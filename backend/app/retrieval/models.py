"""Typed retrieval, evidence, context-package, and local tool values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.documents.models import DocumentView

RetrievalMode = Literal["lexical", "semantic", "hybrid"]
SemanticStatus = Literal["disabled", "available", "unavailable"]
EvidenceSourceType = Literal["professor_document"]


class ModuleSourceReference(BaseModel):
    """A safe Canvas module location without inert Canvas URLs."""

    model_config = ConfigDict(frozen=True)

    canvas_course_id: str
    canvas_module_id: str
    canvas_module_item_id: str
    module_name: str | None = None
    item_title: str | None = None


class EvidenceReference(BaseModel):
    """Provider-neutral evidence sufficient to display and verify a source."""

    model_config = ConfigDict(frozen=True)

    citation_id: str
    authority: Literal["professor_material"] = "professor_material"
    source_type: EvidenceSourceType
    canvas_course_id: str | None = None
    canvas_file_id: str | None = None
    canvas_assignment_id: str | None = None
    change_event_id: int | None = None
    display_name: str | None = None
    filename: str | None = None
    unit_type: str | None = None
    unit_index: int | None = None
    page_number: int | None = None
    slide_number: int | None = None
    heading: str | None = None
    source_sha256: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    is_stale: bool = False
    module_references: tuple[ModuleSourceReference, ...] = ()


class RetrievalSignal(BaseModel):
    """One inspectable ranking contribution."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["lexical", "semantic"]
    rank: int = Field(ge=1)
    raw_score: float
    provider_id: str | None = None
    model_version: str | None = None


class RetrievalHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: EvidenceReference
    snippet: str = Field(max_length=1000)
    fusion_score: float
    signals: tuple[RetrievalSignal, ...]


class RetrievalResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    mode: RetrievalMode
    semantic_status: SemanticStatus
    results: tuple[RetrievalHit, ...]
    index_limitation: str | None = None


class ContextEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: EvidenceReference
    excerpt: str = Field(max_length=4000)
    retrieval_signals: tuple[RetrievalSignal, ...]


class RetrievalContextPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    mode: RetrievalMode
    semantic_status: SemanticStatus
    authority: Literal["professor_material"] = "professor_material"
    evidence: tuple[ContextEvidence, ...]
    max_characters: int
    characters_used: int
    truncated: bool
    no_evidence: bool


class UnitContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: EvidenceReference
    text: str = Field(max_length=4000)
    text_fingerprint: str


class UnitNeighborhood(BaseModel):
    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    center_unit_index: int
    units: tuple[UnitContext, ...]
    truncated: bool


class SourceDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    document: DocumentView
    authority: Literal["professor_material"] = "professor_material"
    citations: tuple[EvidenceReference, ...]
