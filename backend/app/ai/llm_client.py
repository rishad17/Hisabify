"""Minimal Gemini REST client for *structured* (JSON-schema constrained) output.

Why REST + httpx instead of an SDK: it's ~100 lines you can read end to end, easy to
fake in tests (httpx.MockTransport), and swapping providers later means rewriting only
this file — the rest of the app depends on the `LLMClient` protocol below.

Reliability:
  * every call has a timeout
  * HTTP 429/500/503 or a timeout on the primary model → retry once on the fallback model
  * the response must be valid JSON; otherwise LLMError is raised (never half-parsed data)
"""

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    """The AI provider failed or returned something unusable."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class LLMResult:
    data: dict[str, Any]
    model: str
    latency_ms: int
    tokens_in: int | None
    tokens_out: int | None


class LLMClient(Protocol):
    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        audio: tuple[bytes, str] | None = None,
    ) -> LLMResult: ...


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        fallback_model: str | None = None,
        timeout_seconds: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.models = [model] + ([fallback_model] if fallback_model else [])
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            transport=transport,
        )

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        temperature: float = 0.1,
        audio: tuple[bytes, str] | None = None,
    ) -> LLMResult:
        """`audio` = (bytes, mime type) is sent inline with the text, e.g. for transcription."""
        parts: list[dict[str, Any]] = [{"text": user}]
        if audio is not None:
            data, mime = audio
            parts.append(
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}
            )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        payload, model, latency_ms = self._with_fallback(body)
        try:
            candidate = payload["candidates"][0]
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"])
            data = json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            reason = payload.get("candidates", [{}])[0].get("finishReason", "unknown")
            raise LLMError(f"{model} returned no usable JSON (finish: {reason})") from exc
        if not isinstance(data, dict):
            raise LLMError(f"{model} returned JSON that is not an object")
        usage = payload.get("usageMetadata", {})
        return LLMResult(
            data=data,
            model=payload.get("modelVersion", model),
            latency_ms=latency_ms,
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
        )

    def generate_turn(
        self,
        *,
        system: str,
        contents: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.2,
        model: str | None = None,
        allow_tools: bool = True,
    ) -> "TurnResult":
        """One step of a function-calling conversation.

        The model either asks to call tools (`function_calls`) or answers (`text`).
        `content` is the model's message exactly as returned — append it to `contents`
        unchanged (Gemini 3 attaches "thought signatures" that must be sent back).
        Pass `model` to stay on the model that started the conversation.
        """
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": tools}],
            # NONE forces a plain-text answer (used on the final round).
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO" if allow_tools else "NONE"}},
            "generationConfig": {"temperature": temperature},
        }
        payload, used, latency_ms = self._with_fallback(body, only=model)
        try:
            content = payload["candidates"][0]["content"]
            parts = content.get("parts", [])
        except (KeyError, IndexError, TypeError) as exc:
            reason = payload.get("candidates", [{}])[0].get("finishReason", "unknown")
            raise LLMError(f"{used} returned no content (finish: {reason})") from exc
        calls = [
            (p["functionCall"].get("name", ""), p["functionCall"].get("args") or {})
            for p in parts
            if isinstance(p.get("functionCall"), dict)
        ]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        usage = payload.get("usageMetadata", {})
        return TurnResult(
            content={"role": "model", "parts": parts},
            function_calls=calls,
            text=text,
            model=used,
            latency_ms=latency_ms,
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
        )

    def _with_fallback(
        self, body: dict[str, Any], only: str | None = None
    ) -> tuple[dict[str, Any], str, int]:
        models = [only] if only else self.models
        last_error: LLMError | None = None
        for model in models:
            try:
                payload, latency_ms = self._post(model, body)
                return payload, model, latency_ms
            except LLMError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
                logger.warning("Gemini model %s failed (%s); trying fallback", model, exc)
        assert last_error is not None
        raise last_error

    def _post(self, model: str, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        start = time.perf_counter()
        try:
            response = self._http.post(GEMINI_URL.format(model=model), json=body)
        except httpx.TimeoutException as exc:
            raise LLMError(f"{model} timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Network error calling {model}: {exc}", retryable=True) from exc
        latency_ms = int((time.perf_counter() - start) * 1000)
        if response.status_code != 200:
            raise LLMError(
                f"{model} returned HTTP {response.status_code}",
                retryable=response.status_code in RETRYABLE_STATUS,
            )
        return response.json(), latency_ms


@dataclass
class TurnResult:
    content: dict[str, Any]
    function_calls: list[tuple[str, dict[str, Any]]]
    text: str
    model: str
    latency_ms: int
    tokens_in: int | None
    tokens_out: int | None
