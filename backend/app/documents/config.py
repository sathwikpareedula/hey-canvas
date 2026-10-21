"""Document parser limits derived from validated application settings."""

from app.config import Settings
from app.documents.models import DocumentLimits


def document_limits(settings: Settings) -> DocumentLimits:
    return DocumentLimits(
        max_source_bytes=settings.max_canvas_file_bytes,
        max_characters=settings.max_document_characters,
        max_units=settings.max_document_units,
        max_unit_characters=settings.max_document_unit_characters,
        max_archive_entries=settings.max_document_archive_entries,
        max_archive_uncompressed_bytes=settings.max_document_archive_uncompressed_bytes,
        max_archive_ratio=settings.max_document_archive_ratio,
    )
