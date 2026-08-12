"""BYOK (Bring Your Own Key) chat-completion providers.

The API key always arrives with the request from the browser and is never
written to disk, logged, or cached server-side — each call is stateless.
Swapping/adding a provider means adding one function here; the chat API
route and the retrieval pipeline never change.
"""
from __future__ import annotations

import httpx

from app.core.errors import InvalidApiKey, LLMProviderError

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "gemini": "gemini-3.6-flash",
}


def _redact(detail: str) -> str:
    # Never let a provider's raw error body (which can echo request headers)
    # leak an API key back to the client.
    return detail[:300]


async def _call_openai(system_prompt: str, user_prompt: str, api_key: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                },
            )
        except httpx.RequestError as e:
            raise LLMProviderError(f"Could not reach OpenAI: {e}") from e

    if resp.status_code in (401, 403):
        raise InvalidApiKey("OpenAI rejected this API key.")
    if resp.status_code >= 400:
        raise LLMProviderError(f"OpenAI error ({resp.status_code}): {_redact(resp.text)}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LLMProviderError("OpenAI returned an unexpected response shape.") from e


async def _call_anthropic(system_prompt: str, user_prompt: str, api_key: str, model: str) -> str:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
        except httpx.RequestError as e:
            raise LLMProviderError(f"Could not reach Anthropic: {e}") from e

    if resp.status_code in (401, 403):
        raise InvalidApiKey("Anthropic rejected this API key.")
    if resp.status_code >= 400:
        raise LLMProviderError(f"Anthropic error ({resp.status_code}): {_redact(resp.text)}")

    data = resp.json()
    try:
        parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
        return "".join(parts).strip()
    except (KeyError, TypeError) as e:
        raise LLMProviderError("Anthropic returned an unexpected response shape.") from e


async def _call_gemini(system_prompt: str, user_prompt: str, api_key: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.post(
                url,
                params={"key": api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"temperature": 0.3},
                },
            )
        except httpx.RequestError as e:
            raise LLMProviderError(f"Could not reach Gemini: {e}") from e

    if resp.status_code in (401, 403):
        raise InvalidApiKey("Gemini rejected this API key.")
    if resp.status_code >= 400:
        raise LLMProviderError(f"Gemini error ({resp.status_code}): {_redact(resp.text)}")

    data = resp.json()
    try:
        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise LLMProviderError("Gemini returned an unexpected response shape.") from e


async def generate_answer(
    provider: str, system_prompt: str, user_prompt: str, api_key: str, model: str | None
) -> tuple[str, str]:
    """Returns (answer_text, model_used). Raises StudioError subclasses on failure."""
    resolved_model = model or DEFAULT_MODELS.get(provider, "")

    if provider == "openai":
        answer = await _call_openai(system_prompt, user_prompt, api_key, resolved_model)
    elif provider == "anthropic":
        answer = await _call_anthropic(system_prompt, user_prompt, api_key, resolved_model)
    elif provider == "gemini":
        answer = await _call_gemini(system_prompt, user_prompt, api_key, resolved_model)
    else:
        raise LLMProviderError(f"Unknown provider: {provider}")

    return answer, resolved_model
