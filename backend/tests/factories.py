"""Builders for real test documents — no fixture files checked into the repo."""

from __future__ import annotations

import io


def make_pdf(pages: list[str]) -> bytes:
    """Build a real multi-page PDF with PyMuPDF."""
    import fitz

    document = fitz.open()
    for body in pages:
        page = document.new_page()
        if body.strip():
            page.insert_text((72, 96), body, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def make_docx(paragraphs: list[str]) -> bytes:
    """Build a real .docx with python-docx."""
    import docx

    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_txt(body: str) -> bytes:
    return body.encode("utf-8")
