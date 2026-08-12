"""Text extraction.

Each loader returns a list of :class:`Segment`. A segment is the smallest unit
that carries its own page number, so PDF chunks can keep the page they came
from. Non-paginated formats return a single segment with ``page=None``.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field

from app.core.errors import (
    EmptyDocument,
    EncryptedDocument,
    ExtractionError,
    UnsupportedFileType,
)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({"pdf", "txt", "md", "docx"})

ALLOWED_MIME_TYPES: dict[str, frozenset[str]] = {
    "pdf": frozenset({"application/pdf", "application/x-pdf"}),
    "txt": frozenset({"text/plain", "application/octet-stream", ""}),
    "md": frozenset(
        {"text/markdown", "text/x-markdown", "text/plain", "application/octet-stream", ""}
    ),
    "docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
            "",
        }
    ),
}

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+(?=\n)")


@dataclass(frozen=True, slots=True)
class Segment:
    """A contiguous run of text with an optional page number."""

    text: str
    page: int | None = None


@dataclass(slots=True)
class ExtractedDocument:
    filename: str
    file_type: str
    segments: list[Segment] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.segments)

    @property
    def page_count(self) -> int | None:
        pages = {s.page for s in self.segments if s.page is not None}
        return len(pages) or None


def sanitize_filename(name: str) -> str:
    """Reduce a client-supplied name to a bare, safe filename.

    Client paths are never trusted: directory components are discarded and the
    result can never traverse upward.
    """
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = _CONTROL_CHARS.sub("", name).strip().strip(".")
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:200] or "untitled"


def get_extension(filename: str) -> str:
    _, _, ext = sanitize_filename(filename).rpartition(".")
    return ext.lower()


def is_supported(filename: str) -> bool:
    return get_extension(filename) in SUPPORTED_EXTENSIONS


def validate_content_type(extension: str, content_type: str | None) -> None:
    """Reject a file whose declared MIME type contradicts its extension."""
    allowed = ALLOWED_MIME_TYPES.get(extension)
    if allowed is None:
        raise UnsupportedFileType(f".{extension} files are not supported.")
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared and declared not in allowed:
        raise UnsupportedFileType(
            f"This file says it is {declared}, which does not match a .{extension} file."
        )


def sniff_matches_extension(extension: str, data: bytes) -> bool:
    """Cheap magic-byte check so a renamed executable cannot pose as a document."""
    if extension == "pdf":
        return data[:5] == b"%PDF-"
    if extension == "docx":
        return data[:2] == b"PK"
    return True  # txt / md are validated by decoding instead


def clean_text(text: str) -> str:
    """Normalise whitespace and drop characters that only add noise."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _ZERO_WIDTH.sub("", text)
    text = _CONTROL_CHARS.sub("", text)
    text = _TRAILING_SPACES.sub("", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# Per-format loaders
# --------------------------------------------------------------------------


def _load_pdf(data: bytes) -> list[Segment]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ExtractionError("PDF support is unavailable on this server.") from exc

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ExtractionError("This PDF could not be opened. It may be corrupted.") from exc

    try:
        if document.needs_pass:
            raise EncryptedDocument(
                "This PDF is password protected. Remove the password and upload it again."
            )
        segments: list[Segment] = []
        for index in range(document.page_count):
            try:
                raw = document.load_page(index).get_text("text")
            except Exception:
                continue  # skip an unreadable page, keep the rest of the document
            cleaned = clean_text(raw)
            if cleaned:
                segments.append(Segment(text=cleaned, page=index + 1))
    finally:
        document.close()

    if not segments:
        raise EmptyDocument(
            "No text could be read from this PDF. It may be a scan that needs OCR."
        )
    return segments


def _load_docx(data: bytes) -> list[Segment]:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ExtractionError("DOCX support is unavailable on this server.") from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(
            "This Word document could not be opened. It may be corrupted."
        ) from exc

    blocks: list[str] = []
    for paragraph in document.paragraphs:  # document order is preserved
        text = paragraph.text.strip()
        if text:
            blocks.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    body = clean_text("\n\n".join(blocks))
    if not body:
        raise EmptyDocument("This Word document contains no readable text.")
    return [Segment(text=body)]


def _load_plain(data: bytes) -> list[Segment]:
    # UTF-16 is only attempted when a byte-order mark says so; guessing it
    # otherwise turns ordinary 8-bit text into CJK gibberish.
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        candidates = ("utf-16", "utf-8", "latin-1")
    else:
        candidates = ("utf-8", "utf-8-sig", "latin-1")

    for encoding in candidates:
        try:
            decoded = data.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:  # pragma: no cover - latin-1 always succeeds
        decoded = data.decode("utf-8", errors="replace")

    body = clean_text(decoded)
    if not body:
        raise EmptyDocument("This file is empty.")
    return [Segment(text=body)]


def load_document(filename: str, data: bytes) -> ExtractedDocument:
    """Extract cleaned text segments from raw file bytes."""
    safe_name = sanitize_filename(filename)
    extension = get_extension(safe_name)

    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            f".{extension} is not a supported format. Upload a PDF, DOCX, TXT, or MD file."
        )
    if not data:
        raise EmptyDocument("This file is empty.")
    if not sniff_matches_extension(extension, data):
        raise UnsupportedFileType(
            f"This file is not a valid .{extension} file despite its name."
        )

    if extension == "pdf":
        segments = _load_pdf(data)
    elif extension == "docx":
        segments = _load_docx(data)
    else:  # txt and md are both read as text; markdown structure is left intact
        segments = _load_plain(data)

    return ExtractedDocument(filename=safe_name, file_type=extension, segments=segments)
