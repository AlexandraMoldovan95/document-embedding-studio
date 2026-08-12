"""Chunking behaviour, offsets, and the guarantees the UI relies on."""

from __future__ import annotations

import pytest

from app.core.errors import InvalidChunkSettings
from app.services.chunking import (
    chunk_document,
    chunk_text,
    effective_max_overlap,
    validate_chunk_settings,
)

# Text with no separators, so boundary snapping cannot move the offsets.
SOLID = "a" * 5000


def test_default_settings_offsets() -> None:
    """chunk_size=1000, overlap=200 -> windows start at 0, 800, 1600, ..."""
    chunks = chunk_document(SOLID, 1000, 200)
    assert [c.start for c in chunks] == [0, 800, 1600, 2400, 3200, 4000]
    assert chunks[0].start == 0 and chunks[0].end == 1000
    assert chunks[1].start == 1000 - 200
    assert all(c.size == 1000 for c in chunks[:-1])
    assert chunks[-1].end == len(SOLID)


def test_overlap_content_is_actually_shared() -> None:
    chunks = chunk_document(SOLID[:2000], 1000, 200)
    assert chunks[0].text[-200:] == chunks[1].text[:200]


def test_zero_overlap_produces_disjoint_chunks() -> None:
    chunks = chunk_document(SOLID, 1000, 0)
    assert [c.start for c in chunks] == [0, 1000, 2000, 3000, 4000]
    assert "".join(c.text for c in chunks) == SOLID


def test_overlap_one_below_chunk_size_terminates() -> None:
    """The pathological case: the window advances by exactly one character."""
    text = "b" * 300
    chunks = chunk_document(text, 100, 99)
    assert len(chunks) == len(text) - 100 + 1
    assert chunks[1].start == 1
    assert chunks[-1].end == len(text)


@pytest.mark.parametrize("overlap", [1000, 1500, 2000])
def test_overlap_equal_or_greater_than_chunk_size_is_rejected(overlap: int) -> None:
    with pytest.raises(InvalidChunkSettings):
        chunk_document(SOLID, 1000, overlap)


def test_negative_overlap_is_rejected() -> None:
    with pytest.raises(InvalidChunkSettings):
        validate_chunk_settings(1000, -1)


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_document("", 1000, 200) == []


def test_whitespace_only_text_returns_no_chunks() -> None:
    assert chunk_document("   \n\n\t   \n  ", 1000, 200) == []


def test_text_smaller_than_chunk_size_returns_one_chunk() -> None:
    chunks = chunk_document("short document body", 1000, 200)
    assert len(chunks) == 1
    assert chunks[0].text == "short document body"


def test_no_chunk_is_empty_or_whitespace_only() -> None:
    text = ("paragraph one.\n\n\n" + " " * 400 + "\n\npart two here.\n\n") * 40
    for chunk in chunk_document(text, 300, 60):
        assert chunk.text.strip() == chunk.text
        assert chunk.text != ""


def test_very_long_text_covers_the_whole_document() -> None:
    text = "word " * 200_000  # 1M characters
    chunks = chunk_document(text, 1000, 100)
    assert len(chunks) > 900
    assert chunks[0].start == 0
    assert chunks[-1].end == len(text.rstrip())


def test_boundary_snapping_avoids_cutting_mid_word() -> None:
    sentence = "The quick brown fox jumps over the lazy dog. "
    text = sentence * 60
    chunks = chunk_document(text, 500, 50)
    # A snapped chunk ends at a sentence or word boundary, never inside a word.
    for chunk in chunks[:-1]:
        assert chunk.text[-1] in ".!?" or chunk.text.split()[-1].isalpha()
    assert all(400 <= chunk.size <= 500 for chunk in chunks[:-1])


def test_boundaries_can_be_disabled_for_exact_windows() -> None:
    text = "word " * 500
    chunks = chunk_document(text, 400, 0, respect_boundaries=False)
    assert chunks[1].start == 400


def test_chunk_text_helper_returns_plain_strings() -> None:
    pieces = chunk_text(SOLID[:2500], 1000, 200)
    assert all(isinstance(piece, str) for piece in pieces)
    # windows start at 0, 800, 1600; the third reaches the end of the text
    assert len(pieces) == 3


@pytest.mark.parametrize(
    ("chunk_size", "expected"),
    [(100, 99), (1000, 999), (2001, 2000), (10_000, 2000)],
)
def test_effective_max_overlap(chunk_size: int, expected: int) -> None:
    assert effective_max_overlap(chunk_size) == expected


def test_every_chunk_stays_within_the_configured_size() -> None:
    text = "sentence here. " * 5000
    for chunk in chunk_document(text, 750, 150):
        assert chunk.size <= 750
