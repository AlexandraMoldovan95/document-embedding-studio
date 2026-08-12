"""Tests for POST /api/chat — retrieval + BYOK generation.

The outbound LLM call is monkeypatched so these run offline with no real
API key and no network access, same philosophy as the hashing embedding
provider used for the rest of the suite.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_module
from app.core.errors import InvalidApiKey


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_answer(provider, system_prompt, user_prompt, api_key, model):
        if api_key == "bad-key":
            raise InvalidApiKey(f"{provider} rejected this API key.")
        assert "Question:" in user_prompt
        return f"[stub answer from {provider}] {api_key[:3]}...", model or "stub-model"

    # chat.py imports generate_answer by name, so the patch target is the
    # reference bound in chat.py's own namespace, not the source module.
    monkeypatch.setattr(chat_module, "generate_answer", fake_generate_answer)


def _ingest_sample(client: TestClient, collection: str = "chat_docs") -> None:
    content = (b"Dragons hatch from eggs on flying islands. " * 20)
    client.post(
        "/api/ingest",
        files={"files": ("dragons.txt", content, "text/plain")},
        data={"chunk_size": "300", "chunk_overlap": "50", "collection_name": collection},
    )


def test_chat_answers_with_sources(client: TestClient):
    _ingest_sample(client)
    resp = client.post(
        "/api/chat",
        json={
            "query": "how do dragons hatch?",
            "collection_name": "chat_docs",
            "top_k": 3,
            "provider": "openai",
            "api_key": "sk-test-key",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "openai"
    assert body["answer"].startswith("[stub answer from openai]")
    assert len(body["sources"]) > 0
    assert body["sources"][0]["filename"] == "dragons.txt"


def test_chat_missing_collection_gives_clean_error(client: TestClient):
    resp = client.post(
        "/api/chat",
        json={
            "query": "anything",
            "collection_name": "does_not_exist_yet",
            "provider": "anthropic",
            "api_key": "sk-test-key",
        },
    )
    assert resp.status_code in (404, 422)
    assert resp.json()["success"] is False


def test_chat_bad_api_key_surfaces_401(client: TestClient):
    _ingest_sample(client, collection="chat_docs2")
    resp = client.post(
        "/api/chat",
        json={
            "query": "how do dragons hatch?",
            "collection_name": "chat_docs2",
            "provider": "gemini",
            "api_key": "bad-key",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_api_key"


@pytest.mark.parametrize("llm_provider", ["openai", "anthropic", "gemini"])
def test_chat_supports_all_three_providers(client: TestClient, llm_provider: str):
    _ingest_sample(client, collection=f"chat_{llm_provider}")
    resp = client.post(
        "/api/chat",
        json={
            "query": "where do dragons live?",
            "collection_name": f"chat_{llm_provider}",
            "provider": llm_provider,
            "api_key": "sk-abc123",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["provider"] == llm_provider
