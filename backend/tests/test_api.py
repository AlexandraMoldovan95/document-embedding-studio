"""End-to-end API tests: upload, chunk, embed, store, search, manage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services.vector_store import VectorStore
from tests.factories import make_docx, make_pdf, make_txt

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

LEASE_TEXT = (
    "The tenant shall pay rent on the first day of each calendar month. "
    "Late payment incurs a fee after a grace period of five days. "
) * 20
KITCHEN_TEXT = (
    "Preheat the oven to 200 degrees and roast the vegetables until golden. "
    "Season generously with salt, pepper, and olive oil before serving. "
) * 20


def ingest(
    client: TestClient,
    files: list[tuple[str, tuple[str, bytes, str]]],
    **data: object,
):
    payload = {"chunk_size": 1000, "chunk_overlap": 200, "collection_name": "documents"}
    payload.update(data)
    return client.post("/api/ingest", files=files, data=payload)


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------
def test_ingest_pdf_stores_chunks_with_page_metadata(client: TestClient) -> None:
    pdf = make_pdf([f"Page {n} content. " + LEASE_TEXT for n in range(1, 4)])
    response = ingest(client, [("files", ("contract.pdf", pdf, PDF_MIME))])

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["documents_processed"] == 1
    assert body["chunks_created"] > 0
    assert body["chunks_created"] == body["embeddings_created"]
    assert body["characters_extracted"] > 0
    assert body["duration_seconds"] >= 0
    assert body["errors"] == []

    pages = {chunk["page"] for chunk in body["chunks"]}
    assert pages == {1, 2, 3}
    first = body["chunks"][0]
    assert first["filename"] == "contract.pdf"
    assert first["file_type"] == "pdf"
    assert first["id"].endswith("_chunk_0")


def test_ingest_multiple_formats_at_once(client: TestClient) -> None:
    response = ingest(
        client,
        [
            ("files", ("notes.txt", make_txt(LEASE_TEXT), "text/plain")),
            ("files", ("guide.md", make_txt("# Guide\n\n" + KITCHEN_TEXT), "text/markdown")),
            ("files", ("report.docx", make_docx([LEASE_TEXT, KITCHEN_TEXT]), DOCX_MIME)),
            ("files", ("manual.pdf", make_pdf([KITCHEN_TEXT]), PDF_MIME)),
        ],
    )
    body = response.json()
    assert body["documents_processed"] == 4
    assert body["documents_failed"] == 0
    assert {f["file_type"] for f in body["files"]} == {"txt", "md", "docx", "pdf"}
    assert all(f["status"] == "indexed" for f in body["files"])


def test_chunk_settings_actually_change_the_output(client: TestClient) -> None:
    body_small = ingest(
        client,
        [("files", ("a.txt", make_txt(LEASE_TEXT), "text/plain"))],
        chunk_size=200,
        chunk_overlap=0,
        collection_name="small",
    ).json()
    body_large = ingest(
        client,
        [("files", ("a.txt", make_txt(LEASE_TEXT), "text/plain"))],
        chunk_size=2000,
        chunk_overlap=0,
        collection_name="large",
    ).json()

    assert body_small["chunks_created"] > body_large["chunks_created"]
    assert all(chunk["char_count"] <= 200 for chunk in body_small["chunks"])
    assert body_small["chunks"][0]["text"] != body_large["chunks"][0]["text"]


def test_one_bad_file_does_not_stop_the_others(client: TestClient) -> None:
    response = ingest(
        client,
        [
            ("files", ("good.txt", make_txt(LEASE_TEXT), "text/plain")),
            ("files", ("broken.pdf", b"%PDF-1.4 corrupted", PDF_MIME)),
            ("files", ("also-good.md", make_txt(KITCHEN_TEXT), "text/markdown")),
        ],
    )
    body = response.json()
    assert response.status_code == 200
    assert body["documents_processed"] == 2
    assert body["documents_failed"] == 1
    assert body["errors"][0]["filename"] == "broken.pdf"
    statuses = {f["filename"]: f["status"] for f in body["files"]}
    assert statuses == {"good.txt": "indexed", "broken.pdf": "error", "also-good.md": "indexed"}


def test_unsupported_file_is_reported_at_file_level(client: TestClient) -> None:
    response = ingest(
        client,
        [
            ("files", ("script.exe", b"MZ\x90\x00binary", "application/octet-stream")),
            ("files", ("ok.txt", make_txt(LEASE_TEXT), "text/plain")),
        ],
    )
    body = response.json()
    assert body["documents_failed"] == 1
    assert body["errors"][0]["code"] == "unsupported_file_type"
    assert body["documents_processed"] == 1


def test_empty_document_is_reported(client: TestClient) -> None:
    body = ingest(client, [("files", ("blank.txt", b"   \n  ", "text/plain"))]).json()
    assert body["success"] is False
    assert body["errors"][0]["code"] in {"empty_document", "error"}


def test_duplicate_upload_in_one_request_is_flagged(client: TestClient) -> None:
    data = make_txt(LEASE_TEXT)
    body = ingest(
        client,
        [
            ("files", ("dup.txt", data, "text/plain")),
            ("files", ("dup.txt", data, "text/plain")),
        ],
    ).json()
    assert body["documents_processed"] == 1
    assert body["documents_failed"] == 1


def test_oversized_file_is_rejected(client: TestClient) -> None:
    huge = make_txt("x" * (6 * 1024 * 1024))  # limit is 5 MB in tests
    response = ingest(client, [("files", ("huge.txt", huge, "text/plain"))])
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


def test_invalid_chunk_parameters_are_rejected(client: TestClient) -> None:
    response = ingest(
        client,
        [("files", ("a.txt", make_txt(LEASE_TEXT), "text/plain"))],
        chunk_size=500,
        chunk_overlap=500,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] in {"invalid_chunk_settings", "invalid_request"}
    assert "overlap" in body["message"].lower()


def test_chunk_size_below_minimum_is_rejected(client: TestClient) -> None:
    response = ingest(
        client,
        [("files", ("a.txt", make_txt(LEASE_TEXT), "text/plain"))],
        chunk_size=10,
        chunk_overlap=0,
    )
    assert response.status_code == 422


def test_invalid_collection_name_is_rejected(client: TestClient) -> None:
    response = ingest(
        client,
        [("files", ("a.txt", make_txt(LEASE_TEXT), "text/plain"))],
        collection_name="no spaces!",
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_collection_name"


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------
def test_semantic_search_finds_the_relevant_document(client: TestClient) -> None:
    ingest(
        client,
        [
            ("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain")),
            ("files", ("recipes.txt", make_txt(KITCHEN_TEXT), "text/plain")),
        ],
    )
    response = client.post(
        "/api/search",
        json={"query": "rent payment late fee", "collection_name": "documents", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 3
    top = body["results"][0]
    assert top["filename"] == "lease.txt"
    assert top["rank"] == 1
    assert 0.0 <= top["score"] <= 1.0
    assert top["chunk_index"] is not None
    assert body["took_ms"] >= 0


def test_search_respects_top_k(client: TestClient) -> None:
    ingest(client, [("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain"))])
    body = client.post(
        "/api/search", json={"query": "rent", "collection_name": "documents", "top_k": 2}
    ).json()
    assert len(body["results"]) <= 2


def test_search_can_filter_by_filename(client: TestClient) -> None:
    ingest(
        client,
        [
            ("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain")),
            ("files", ("recipes.txt", make_txt(KITCHEN_TEXT), "text/plain")),
        ],
    )
    body = client.post(
        "/api/search",
        json={"query": "anything", "collection_name": "documents", "filename": "recipes.txt"},
    ).json()
    assert body["results"]
    assert {r["filename"] for r in body["results"]} == {"recipes.txt"}


def test_search_on_empty_collection_returns_no_results(client: TestClient) -> None:
    client.post("/api/collections", json={"name": "brandnew"})
    body = client.post(
        "/api/search", json={"query": "anything", "collection_name": "brandnew"}
    ).json()
    assert body["results"] == []


def test_search_on_missing_collection_is_a_clean_404(client: TestClient) -> None:
    response = client.post(
        "/api/search", json={"query": "hello", "collection_name": "does-not-exist"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "collection_not_found"


def test_blank_query_is_rejected(client: TestClient) -> None:
    assert client.post("/api/search", json={"query": ""}).status_code == 422


# --------------------------------------------------------------------------
# Collections
# --------------------------------------------------------------------------
def test_create_list_and_delete_collection(client: TestClient) -> None:
    created = client.post("/api/collections", json={"name": "research"})
    assert created.status_code == 201
    assert created.json()["name"] == "research"

    names = [c["name"] for c in client.get("/api/collections").json()["collections"]]
    assert "research" in names

    assert client.post("/api/collections", json={"name": "research"}).status_code == 409

    deleted = client.delete("/api/collections/research")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True
    assert "research" not in [
        c["name"] for c in client.get("/api/collections").json()["collections"]
    ]


def test_delete_missing_collection_is_a_clean_404(client: TestClient) -> None:
    assert client.delete("/api/collections/nothing-here").status_code == 404


def test_collection_name_validation(client: TestClient) -> None:
    for bad in ["ab", "has space", "-leading", "trailing-", "a" * 64, "1.2.3.4"]:
        response = client.post("/api/collections", json={"name": bad})
        assert response.status_code == 422, bad


def test_stats_report_documents_and_chunks(client: TestClient) -> None:
    ingest(
        client,
        [
            ("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain")),
            ("files", ("recipes.txt", make_txt(KITCHEN_TEXT), "text/plain")),
        ],
    )
    stats = client.get("/api/collections/documents/stats").json()
    assert stats["document_count"] == 2
    assert stats["chunk_count"] > 0
    assert sorted(stats["filenames"]) == ["lease.txt", "recipes.txt"]


def test_chunks_endpoint_pages_through_results(client: TestClient) -> None:
    ingest(
        client,
        [("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain"))],
        chunk_size=200,
        chunk_overlap=20,
    )
    page = client.get("/api/collections/documents/chunks?limit=3&offset=0").json()
    assert len(page["chunks"]) == 3
    assert page["total"] > 3
    assert page["chunks"][0]["text"]

    second = client.get("/api/collections/documents/chunks?limit=3&offset=3").json()
    assert {c["id"] for c in second["chunks"]}.isdisjoint({c["id"] for c in page["chunks"]})


# --------------------------------------------------------------------------
# Persistence and meta
# --------------------------------------------------------------------------
def test_vectors_survive_a_restart(
    client: TestClient, chroma_dir: Path, provider  # noqa: ANN001
) -> None:
    """A brand-new client on the same directory still sees the same vectors."""
    ingest(client, [("files", ("lease.txt", make_txt(LEASE_TEXT), "text/plain"))])
    original = client.get("/api/collections/documents/stats").json()["chunk_count"]

    reopened = VectorStore(chroma_dir)  # fresh process-equivalent client
    assert reopened.count("documents") == original
    matches = reopened.query("documents", provider.embed_query("rent payment"), 3)
    assert matches and matches[0].metadata["filename"] == "lease.txt"


def test_health_and_config(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert sorted(config["supported_extensions"]) == ["docx", "md", "pdf", "txt"]
    assert config["default_chunk_size"] == 1000
    assert config["default_chunk_overlap"] == 200
    assert config["max_overlap"] == 2000
