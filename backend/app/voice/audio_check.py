"""Deterministic loudness check for WAV uploads — runs BEFORE any AI is called.

Why: given pure silence, an LLM transcriber may *hallucinate* a plausible sentence
(we observed "bKash-e 500 taka pathalam" from an all-zero recording). For a finance app
that's unacceptable, so silent recordings are rejected here, in plain Python.

Method: split the audio into 100 ms windows, compute each window's RMS level, and take
the loudest window. Speech peaks far above a quiet room; silence/hiss stays low.
"""

import io
import math
import wave
from array import array

# 16-bit full scale is 32767. 300 ≈ −40 dBFS: quieter than any normal speech close to a
# phone/laptop mic, louder than a typical silent room (browser AGC is usually on).
SPEECH_RMS_THRESHOLD = 300


class InvalidWav(ValueError):
    pass


def loudest_window_rms(wav_bytes: bytes, window_ms: int = 100) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            if w.getsampwidth() != 2:
                raise InvalidWav("expected 16-bit PCM")
            channels, rate = w.getnchannels(), w.getframerate()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise InvalidWav(str(exc)) from exc

    samples = array("h")
    samples.frombytes(frames[: len(frames) - len(frames) % 2])
    if channels > 1:
        samples = samples[::channels]  # first channel is enough for a loudness check
    if not samples:
        return 0.0

    window = max(1, rate * window_ms // 1000)
    loudest = 0.0
    for start in range(0, len(samples), window):
        chunk = samples[start : start + window]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
        loudest = max(loudest, rms)
    return loudest


def is_probably_silent(wav_bytes: bytes) -> bool:
    return loudest_window_rms(wav_bytes) < SPEECH_RMS_THRESHOLD
