"""Optional local semantic retrieval interfaces and index identity contracts."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingIdentity(BaseModel):
    """Identity needed to invalidate only derived data for a changed unit."""

    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    unit_index: int
    source_sha256: str
    parser_version: str
    text_fingerprint: str
    provider_id: str
    model_version: str


class SemanticMatch(BaseModel):
    """A provider candidate that must be verified against current local units."""

    model_config = ConfigDict(frozen=True)

    canvas_file_id: str
    unit_index: int
    source_sha256: str
    text_fingerprint: str
    score: float = Field(ge=0)


class SemanticIndexUnit(BaseModel):
    """One authoritative Phase 8 unit supplied to a local index implementation."""

    model_config = ConfigDict(frozen=True)

    identity: EmbeddingIdentity
    text: str


class SemanticIndexSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: int
    updated: int
    unchanged: int
    removed: int


class SemanticProviderUnavailable(RuntimeError):
    """The configured local semantic provider is unavailable without data egress."""


class SemanticSearchProvider(Protocol):
    """Local-only provider boundary; implementations must not send source text externally."""

    @property
    def provider_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def search(
        self,
        query: str,
        *,
        canvas_course_id: str | None,
        canvas_file_id: str | None,
        limit: int,
    ) -> list[SemanticMatch]: ...


class SemanticIndexProvider(SemanticSearchProvider, Protocol):
    """Future local index lifecycle boundary keyed by complete derivation identity."""

    def synchronize(self, units: list[SemanticIndexUnit]) -> SemanticIndexSummary:
        """Synchronize a bounded authoritative unit set without external data egress."""
