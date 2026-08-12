"""Character-based text chunking.

The window is measured in characters, exactly as configured in the UI. Each
window may be pulled back to a nearby natural boundary (paragraph break, line
break, sentence ending, whitespace) so chunks do not end mid-word, but the
window never grows past ``chunk_size`` and never shrinks below the search
window, so chunk sizes stay close to the configured value.

Progress invariant: the next window always starts at least one character after
the current one, so the loop terminates for every ``0 <= overlap < chunk_size``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import InvalidChunkSettings

# Ordered by preference: a paragraph break is a better cut than a bare space.
_BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\n\s*\n"),  # paragraph break
    # Sentence ending. Two fixed-width lookbehinds because Python's `re` does
    # not allow a variable-width one.
    re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"')\]]))\s"),
    re.compile(r"\n"),  # line break
    re.compile(r"\s"),  # any whitespace
)

# How far back from the hard limit we are willing to look for a nicer cut,
# as a fraction of chunk_size, and as an absolute ceiling.
_LOOKBACK_RATIO = 0.2
_LOOKBACK_MAX = 300


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk plus its character offsets in the source text."""

    text: str
    start: int
    end: int

    @property
    def size(self) -> int:
        return len(self.text)


def validate_chunk_settings(chunk_size: int, overlap: int) -> None:
    """Raise if the pair (chunk_size, overlap) could not produce valid chunks."""
    if chunk_size <= 0:
        raise InvalidChunkSettings("Chunk size must be greater than 0.")
    if overlap < 0:
        raise InvalidChunkSettings("Chunk overlap cannot be negative.")
    if overlap >= chunk_size:
        raise InvalidChunkSettings(
            f"Chunk overlap must be smaller than chunk size "
            f"(got overlap={overlap}, chunk size={chunk_size})."
        )


def effective_max_overlap(chunk_size: int, ceiling: int = 2000) -> int:
    """The largest overlap the UI may offer for a given chunk size."""
    return max(0, min(ceiling, chunk_size - 1))


def _find_boundary(text: str, window_start: int, window_end: int) -> int | None:
    """Return the best cut point inside ``[window_start, window_end)``.

    The cut point is the offset *after* the separator, so the separator stays
    with the chunk that precedes it.
    """
    segment = text[window_start:window_end]
    for pattern in _BOUNDARY_PATTERNS:
        match = None
        for match in pattern.finditer(segment):  # keep the last match
            pass
        if match is not None:
            cut = window_start + match.end()
            if cut > window_start:
                return cut
    return None


def _trimmed_span(text: str, start: int, end: int) -> tuple[str, int, int] | None:
    """Strip surrounding whitespace and return the piece with real offsets."""
    left, right = start, end
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left >= right:
        return None
    return text[left:right], left, right


def chunk_document(
    text: str,
    chunk_size: int,
    overlap: int,
    *,
    respect_boundaries: bool = True,
) -> list[TextChunk]:
    """Split ``text`` into overlapping character windows."""
    validate_chunk_settings(chunk_size, overlap)

    if not text or not text.strip():
        return []

    length = len(text)
    lookback = min(_LOOKBACK_MAX, int(chunk_size * _LOOKBACK_RATIO))
    chunks: list[TextChunk] = []
    start = 0

    while start < length:
        hard_end = min(start + chunk_size, length)

        end = hard_end
        if respect_boundaries and hard_end < length and lookback > 0:
            boundary = _find_boundary(text, max(start + 1, hard_end - lookback), hard_end)
            if boundary is not None:
                end = boundary

        span = _trimmed_span(text, start, end)
        if span is not None:
            chunk_text_value, real_start, real_end = span
            chunks.append(TextChunk(chunk_text_value, real_start, real_end))

        if end >= length:
            break

        # Always move forward by at least one character.
        start = max(end - overlap, start + 1)

    return chunks


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Spec-shaped helper: ``(text, chunk_size, overlap) -> list[str]``."""
    return [c.text for c in chunk_document(text, chunk_size, overlap)]
