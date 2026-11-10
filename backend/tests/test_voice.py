"""Voice transcription: provider fallback + upload validation. No DB, no network."""

import io
import struct
import wave

import httpx
import pytest

from app.ai.llm_client import LLMError, LLMResult
from app.ai.rate_limit import RateLimiter
from app.voice.transcriber import (
    NoSpeechError,
    SpeechTranscriber,
    Transcript,
    TranscriptionError,
)
from tests.conftest import auth_header

URL = "/api/v1/ai/transcribe"


def make_wav(seconds: float = 1.0, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))
    return buffer.getvalue()


def tone_wav(amplitude: int, seconds: float = 1.0, rate: int = 16_000) -> bytes:
    import math

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 220 * i / rate)))
            for i in range(int(seconds * rate))
        )
        w.writeframes(frames)
    return buffer.getvalue()


class FakeLLM:
    def __init__(self, data=None, error=None):
        self.data, self.error, self.calls = data, error, []

    def generate_json(self, *, system, user, schema, temperature=0.1, audio=None):
        self.calls.append({"audio": audio, "system": system})
        if self.error:
            raise self.error
        return LLMResult(self.data, "gemini-fake", 10, 1, 1)


# ------------------------------------------------------------------ transcriber


def test_gemini_transcribes_and_receives_audio():
    llm = FakeLLM({"has_speech": True, "text": " আজকে 50 টাকা cha ", "language": "mixed"})
    result = SpeechTranscriber(llm).transcribe(b"wav-bytes", "audio/wav")
    assert result == Transcript("আজকে 50 টাকা cha", "mixed", "gemini-fake")
    assert llm.calls[0]["audio"] == (b"wav-bytes", "audio/wav")
    assert "Bangla script" in llm.calls[0]["system"]


@pytest.mark.parametrize(
    "data",
    [
        {"has_speech": False, "text": "", "language": "unknown"},
        {"has_speech": True, "text": "   ", "language": "bn"},
    ],
)
def test_no_speech(data):
    with pytest.raises(NoSpeechError):
        SpeechTranscriber(FakeLLM(data)).transcribe(b"x", "audio/wav")


def test_falls_back_to_groq_when_gemini_fails():
    seen = {}

    def groq(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "ajke 50 taka cha"})

    t = SpeechTranscriber(
        FakeLLM(error=LLMError("busy", retryable=True)),
        groq_api_key="gsk_test",
        groq_transport=httpx.MockTransport(groq),
    )
    result = t.transcribe(b"wav-bytes", "audio/wav")
    assert result.text == "ajke 50 taka cha" and result.provider.startswith("groq/")
    assert seen["auth"] == "Bearer gsk_test"
    assert b"whisper-large-v3-turbo" in seen["body"]


def test_all_providers_fail():
    def groq(request):
        return httpx.Response(503)

    t = SpeechTranscriber(
        FakeLLM(error=LLMError("busy", retryable=True)),
        groq_api_key="gsk_test",
        groq_transport=httpx.MockTransport(groq),
    )
    with pytest.raises(TranscriptionError):
        t.transcribe(b"x", "audio/wav")


def test_gemini_client_sends_audio_inline():
    import base64
    import json

    from app.ai.llm_client import GeminiClient

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        payload = {"has_speech": True, "text": "hi", "language": "en"}
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
        )

    client = GeminiClient("k", "m", transport=httpx.MockTransport(handler))
    SpeechTranscriber(client).transcribe(b"\x01\x02", "audio/wav")
    part = captured["body"]["contents"][0]["parts"][1]["inline_data"]
    assert part == {"mime_type": "audio/wav", "data": base64.b64encode(b"\x01\x02").decode()}


# ------------------------------------------------------------------ endpoint


class FakeTranscriber:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    def transcribe(self, audio: bytes, mime_type: str) -> Transcript:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result or Transcript("আজকে 50 টাকা cha", "mixed", "fake")


@pytest.fixture
def voice(client, make_token):
    def _setup(transcriber=None, limit=100):
        client.app.state.transcriber = transcriber or FakeTranscriber()
        client.app.state.ai_rate_limiter = RateLimiter(limit)
        headers = auth_header(make_token())

        def upload(data: bytes, mime: str = "audio/wav"):
            return client.post(URL, headers=headers, files={"audio": ("v.wav", data, mime)})

        return upload

    return _setup


def test_transcribe_success(voice):
    r = voice()(tone_wav(3000))
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "আজকে 50 টাকা cha", "language": "mixed", "provider": "fake"}


@pytest.mark.parametrize(
    "data, mime, status, code",
    [
        (make_wav(0.1), "audio/wav", 422, "audio_too_short"),
        (make_wav(80), "audio/wav", 413, "audio_too_large"),
        (b"RIFX" + b"\x00" * 20_000, "audio/wav", 422, "invalid_audio"),
        (tone_wav(3000), "text/plain", 415, "unsupported_audio"),
        (tone_wav(3000), "video/mp4", 415, "unsupported_audio"),
    ],
)
def test_upload_validation(voice, data, mime, status, code):
    fake = FakeTranscriber()
    r = voice(fake)(data, mime)
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert fake.calls == 0  # rejected before any provider is called


def test_webm_accepted_with_codec_suffix(voice):
    assert (
        voice()(b"\x1a\x45\xdf\xa3" + b"\x00" * 20_000, "audio/webm;codecs=opus").status_code == 200
    )


def test_no_speech_and_provider_failure(voice):
    r = voice(FakeTranscriber(error=NoSpeechError()))(tone_wav(3000))
    assert (r.status_code, r.json()["error"]["code"]) == (422, "no_speech")
    r = voice(FakeTranscriber(error=TranscriptionError("down")))(tone_wav(3000))
    assert (r.status_code, r.json()["error"]["code"]) == (503, "transcription_unavailable")


def test_requires_auth_and_rate_limit(client, voice):
    assert (
        client.post(URL, files={"audio": ("v.wav", tone_wav(3000), "audio/wav")}).status_code == 401
    )
    upload = voice(limit=1)
    assert upload(tone_wav(3000)).status_code == 200
    assert upload(tone_wav(3000)).json()["error"]["code"] == "rate_limited"


def test_not_configured(client, make_token):
    client.app.state.transcriber = None
    r = client.post(
        URL, headers=auth_header(make_token()), files={"audio": ("v.wav", make_wav(), "audio/wav")}
    )
    assert r.json()["error"]["code"] == "voice_not_configured"


# ------------------------------------------------------------------ silence guard


def test_silent_wav_rejected_before_ai_is_called(voice):
    """Regression: a real model hallucinated 'bKash-e 500 taka pathalam' from silence."""
    fake = FakeTranscriber()
    r = voice(fake)(make_wav(2.0))
    assert (r.status_code, r.json()["error"]["code"]) == (422, "no_speech")
    assert fake.calls == 0


def test_loud_enough_audio_reaches_transcriber(voice):
    fake = FakeTranscriber()
    assert voice(fake)(tone_wav(3000)).status_code == 200
    assert fake.calls == 1


def test_loudness_measure():
    from app.voice.audio_check import SPEECH_RMS_THRESHOLD, is_probably_silent, loudest_window_rms

    assert loudest_window_rms(make_wav()) == 0
    assert is_probably_silent(tone_wav(100))  # faint hum
    assert not is_probably_silent(tone_wav(3000))  # normal speech level
    # A short loud burst inside a long quiet recording still counts as speech.
    quiet, loud = make_wav(3.0), tone_wav(3000, 0.3)
    combined = quiet[:-20000] + loud[44:]
    assert loudest_window_rms(combined) > SPEECH_RMS_THRESHOLD
