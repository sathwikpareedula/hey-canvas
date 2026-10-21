"""Deterministic Windows-safe file naming and storage-root containment."""

import hashlib
import re
import unicodedata
from pathlib import Path

INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_SAFE_FILENAME_LENGTH = 180


def sanitize_filename(value: str | None, *, fallback: str = "download") -> str:
    """Turn display data into one safe filename without flattening normal Unicode."""

    original = value or fallback
    normalized = unicodedata.normalize("NFC", original)
    cleaned = INVALID_WINDOWS_CHARS.sub("_", normalized).strip().rstrip(". ")
    if cleaned in {"", ".", ".."}:
        cleaned = fallback
    stem = cleaned.split(".", 1)[0].upper()
    if stem in RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"
    if len(cleaned) > MAX_SAFE_FILENAME_LENGTH:
        path = Path(cleaned)
        suffix = path.suffix[:20]
        digest = hashlib.sha256(original.encode("utf-8", errors="replace")).hexdigest()[:12]
        available = MAX_SAFE_FILENAME_LENGTH - len(suffix) - len(digest) - 2
        cleaned = f"{path.stem[:max(1, available)]}__{digest}{suffix}"
    return cleaned


def safe_file_id_segment(canvas_file_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", canvas_file_id).strip(". ")
    digest = hashlib.sha256(canvas_file_id.encode()).hexdigest()[:12]
    reserved_stem = cleaned.split(".", 1)[0].upper() in RESERVED_WINDOWS_NAMES
    if not cleaned or cleaned != canvas_file_id or reserved_stem:
        cleaned = f"file-{cleaned[:80] or 'id'}-{digest}"
    return cleaned[:120]


def destination_for(root: Path, *, canvas_file_id: str, filename: str | None) -> Path:
    resolved_root = root.expanduser().resolve(strict=False)
    destination = (
        resolved_root
        / safe_file_id_segment(canvas_file_id)
        / sanitize_filename(filename, fallback=f"file-{safe_file_id_segment(canvas_file_id)}")
    ).resolve(strict=False)
    assert_contained(resolved_root, destination)
    return destination


def resolve_relative_path(root: Path, relative_path: str) -> Path:
    resolved_root = root.expanduser().resolve(strict=False)
    destination = (resolved_root / Path(relative_path)).resolve(strict=False)
    assert_contained(resolved_root, destination)
    return destination


def relative_storage_path(root: Path, destination: Path) -> str:
    resolved_root = root.expanduser().resolve(strict=False)
    resolved_destination = destination.resolve(strict=False)
    assert_contained(resolved_root, resolved_destination)
    return resolved_destination.relative_to(resolved_root).as_posix()


def assert_contained(root: Path, destination: Path) -> None:
    if destination == root or root not in destination.parents:
        raise ValueError("download destination is outside ACADEMIC_FILES_ROOT")
