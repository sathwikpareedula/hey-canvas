from pathlib import Path

import pytest
from app.files.paths import destination_for, sanitize_filename


@pytest.mark.parametrize(
    ("unsafe_name", "forbidden"),
    [
        ("../lecture.pdf", "/"),
        ("..\\lecture.pdf", "\\"),
        (r"C:\\Windows\\secret.txt", ":"),
        (r"\\server\\share\\notes.pdf", "\\"),
        ("a/b.pdf", "/"),
        ("a\\b.pdf", "\\"),
        ("a:b.pdf", ":"),
        ("a?b.pdf", "?"),
        ("a*b.pdf", "*"),
        ('a"b.pdf', '"'),
        ("a<b>.pdf", "<"),
        ("a|b.pdf", "|"),
    ],
)
def test_unsafe_path_characters_are_neutralized(
    unsafe_name: str, forbidden: str, tmp_path: Path
) -> None:
    destination = destination_for(tmp_path, canvas_file_id="7001", filename=unsafe_name)
    assert forbidden not in destination.name
    assert tmp_path.resolve() in destination.parents


@pytest.mark.parametrize("name", ["CON", "PRN.txt", "AUX", "NUL.pdf", "COM1", "LPT1.docx"])
def test_windows_reserved_names_are_neutralized(name: str, tmp_path: Path) -> None:
    destination = destination_for(tmp_path, canvas_file_id="7001", filename=name)
    assert destination.name.startswith("_")
    assert tmp_path.resolve() in destination.parents


@pytest.mark.parametrize("name", ["lecture.pdf.", "lecture.pdf ", ".", ".."])
def test_windows_trailing_and_dot_names_are_safe(name: str, tmp_path: Path) -> None:
    safe = sanitize_filename(name)
    assert safe not in {"", ".", ".."}
    assert not safe.endswith((".", " "))
    destination = destination_for(tmp_path, canvas_file_id="7001", filename=name)
    assert tmp_path.resolve() in destination.parents


def test_unicode_filename_is_preserved(tmp_path: Path) -> None:
    destination = destination_for(tmp_path, canvas_file_id="7001", filename="運動学 — лекция 1.pdf")
    assert destination.name == "運動学 — лекция 1.pdf"


def test_extremely_long_filename_is_deterministically_shortened(tmp_path: Path) -> None:
    first = destination_for(tmp_path, canvas_file_id="7001", filename=f"{'a' * 400}.pdf")
    second = destination_for(tmp_path, canvas_file_id="7001", filename=f"{'a' * 400}.pdf")
    assert first == second
    assert len(first.name) <= 180


def test_duplicate_filename_different_ids_cannot_collide(tmp_path: Path) -> None:
    first = destination_for(tmp_path, canvas_file_id="7001", filename="lecture.pdf")
    second = destination_for(tmp_path, canvas_file_id="7002", filename="lecture.pdf")
    assert first != second
    assert first.parent != second.parent


def test_hostile_file_id_cannot_escape_storage_root(tmp_path: Path) -> None:
    destination = destination_for(tmp_path, canvas_file_id="../../outside", filename="notes.pdf")
    assert tmp_path.resolve() in destination.parents


@pytest.mark.parametrize("file_id", ["CON", "CON.txt", "LPT1.data"])
def test_reserved_windows_file_id_cannot_create_device_directory(
    file_id: str, tmp_path: Path
) -> None:
    destination = destination_for(tmp_path, canvas_file_id=file_id, filename="notes.pdf")
    assert destination.parent.name.startswith("file-")
    assert tmp_path.resolve() in destination.parents
