"""Extraction, sanitisation, and the error paths for damaged files."""

from __future__ import annotations

import pytest

from app.core.errors import EmptyDocument, ExtractionError, UnsupportedFileType
from app.services.document_loader import (
    clean_text,
    get_extension,
    load_document,
    sanitize_filename,
)
from tests.factories import make_docx, make_pdf


def test_txt_extraction() -> None:
    document = load_document("notes.txt", "Hello world\r\n\r\nSecond line".encode())
    assert document.file_type == "txt"
    assert document.segments[0].page is None
    assert "Hello world" in document.segments[0].text


def test_txt_with_invalid_utf8_still_loads() -> None:
    document = load_document("weird.txt", b"caf\xe9 latte")  # latin-1 bytes
    assert "latte" in document.segments[0].text


def test_markdown_keeps_structure() -> None:
    document = load_document("readme.md", b"# Title\n\n- one\n- two\n")
    text = document.segments[0].text
    assert "# Title" in text and "- one" in text


def test_pdf_extraction_keeps_page_numbers() -> None:
    data = make_pdf(["First page text", "Second page text", "Third page text"])
    document = load_document("manual.pdf", data)
    assert document.file_type == "pdf"
    assert [segment.page for segment in document.segments] == [1, 2, 3]
    assert "Second page text" in document.segments[1].text
    assert document.page_count == 3


def test_docx_extraction_preserves_paragraph_order() -> None:
    data = make_docx(["Alpha paragraph", "Beta paragraph", "Gamma paragraph"])
    document = load_document("report.docx", data)
    text = document.segments[0].text
    assert text.index("Alpha") < text.index("Beta") < text.index("Gamma")


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedFileType):
        load_document("payload.exe", b"MZ\x90\x00")


def test_empty_file_is_rejected() -> None:
    with pytest.raises(EmptyDocument):
        load_document("blank.txt", b"")


def test_whitespace_only_file_is_rejected() -> None:
    with pytest.raises(EmptyDocument):
        load_document("blank.txt", b"   \n\n   ")


def test_corrupted_pdf_reports_cleanly() -> None:
    with pytest.raises(ExtractionError):
        load_document("broken.pdf", b"%PDF-1.4 this is not really a pdf")


def test_file_renamed_to_pdf_is_rejected() -> None:
    with pytest.raises(UnsupportedFileType):
        load_document("fake.pdf", b"just plain text, not a pdf at all")


def test_pdf_without_extractable_text_reports_cleanly() -> None:
    with pytest.raises(EmptyDocument):
        load_document("scan.pdf", make_pdf(["", "  "]))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\report.docx", "report.docx"),
        ("  spaced   name.txt  ", "spaced name.txt"),
        ("", "untitled"),
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_get_extension_is_case_insensitive() -> None:
    assert get_extension("REPORT.PDF") == "pdf"


def test_clean_text_collapses_blank_lines_and_strips_controls() -> None:
    assert clean_text("a\x00b\n\n\n\n\nc  \n") == "ab\n\nc"
