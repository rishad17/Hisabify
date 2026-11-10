"""Gemini client behaviour with a fake HTTP transport (no network, no API key needed)."""

import json

import httpx
import pytest

from app.ai.llm_client import GeminiClient, LLMError

SCHEMA = {"type": "OBJECT", "properties": {}}


def ok_response(data: dict, model: str = "gemini-test") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
            "modelVersion": model,
        },
    )


def client(handler) -> GeminiClient:
    return GeminiClient(
        api_key="test-key",
        model="primary",
        fallback_model="backup",
        transport=httpx.MockTransport(handler),
    )


def test_success_parses_json_and_usage():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return ok_response({"intent": "record"})

    result = client(handler).generate_json(system="sys", user="hi", schema=SCHEMA)
    assert result.data == {"intent": "record"}
    assert (result.tokens_in, result.tokens_out) == (100, 20)
    assert "/models/primary:generateContent" in seen["url"]
    assert seen["key"] == "test-key"  # sent as a header, never in the URL
    assert "key=" not in seen["url"]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("status", [429, 503])
def test_overloaded_primary_falls_back(status):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "primary" in request.url.path:
            return httpx.Response(status, json={"error": {"message": "busy"}})
        return ok_response({"ok": True}, model="backup")

    result = client(handler).generate_json(system="s", user="u", schema=SCHEMA)
    assert result.data == {"ok": True} and result.model == "backup"
    assert len(calls) == 2


def test_timeout_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        if "primary" in request.url.path:
            raise httpx.ReadTimeout("slow", request=request)
        return ok_response({"ok": True})

    assert client(handler).generate_json(system="s", user="u", schema=SCHEMA).data == {"ok": True}


def test_both_models_down_raises():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(LLMError):
        client(handler).generate_json(system="s", user="u", schema=SCHEMA)


def test_bad_request_does_not_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad"}})

    with pytest.raises(LLMError):
        client(handler).generate_json(system="s", user="u", schema=SCHEMA)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]},
        {"candidates": [{"finishReason": "SAFETY"}]},
        {"candidates": [{"content": {"parts": [{"text": "[1, 2]"}]}}]},
        {},
    ],
)
def test_unusable_output_raises(payload):
    with pytest.raises(LLMError):
        client(lambda r: httpx.Response(200, json=payload)).generate_json(
            system="s", user="u", schema=SCHEMA
        )
