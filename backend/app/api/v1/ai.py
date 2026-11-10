from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.ai import service
from app.ai.assistant import answer_question
from app.ai.budget_ai import plan_from_text
from app.ai.llm_client import LLMClient
from app.api.v1.transactions import parse_month
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.schemas.ai import (
    AIBudgetIn,
    AIBudgetOut,
    AIMessageIn,
    AIMessageOut,
    AskIn,
    AskOut,
    TranscriptOut,
)
from app.voice.audio_check import InvalidWav, is_probably_silent
from app.voice.transcriber import NoSpeechError, Transcriber, TranscriptionError

router = APIRouter()

# 60 s of 16 kHz mono 16-bit WAV ≈ 1.92 MB. Compressed formats are far smaller.
MAX_AUDIO_BYTES = 2_500_000
MIN_AUDIO_BYTES = 8_000  # ~0.25 s of WAV; anything shorter is an accidental tap
NO_SPEECH_MESSAGE = "I couldn't hear any speech. Try again a little closer to the mic."
ALLOWED_AUDIO = {"audio/wav", "audio/x-wav", "audio/wave", "audio/webm", "audio/ogg", "audio/mp4"}


def get_llm(request: Request) -> LLMClient:
    llm = getattr(request.app.state, "llm", None)
    if llm is None:
        raise AppError("ai_not_configured", "AI is not configured (GEMINI_API_KEY).", 503)
    return llm


def rate_limit(request: Request, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    wait = request.app.state.ai_rate_limiter.check(str(user.id))
    if wait is not None:
        raise AppError(
            "rate_limited",
            f"Too many AI requests. Please wait {int(wait) + 1} seconds.",
            status_code=429,
        )
    return user


@router.post("/message", response_model=AIMessageOut)
def ai_message(
    body: AIMessageIn,
    user: CurrentUser = Depends(rate_limit),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> dict:
    """Understand a message like "ajke 50 taka cha, 100 rickshaw" and return a DRAFT.

    Nothing is saved. Confirm by posting the (possibly edited) items to
    /transactions/batch with `Idempotency-Key: <draft.draft_id>`.
    """
    return service.process_message(
        db,
        user.id,
        body.text,
        llm=llm,
        source=body.source,
        history=[t.model_dump() for t in body.history],
    )


def get_transcriber(request: Request) -> Transcriber:
    transcriber = getattr(request.app.state, "transcriber", None)
    if transcriber is None:
        raise AppError("voice_not_configured", "Voice input is not configured.", 503)
    return transcriber


@router.post("/transcribe", response_model=TranscriptOut)
async def transcribe(
    audio: UploadFile = File(description="Voice note, ideally 16 kHz mono WAV, max 60 s"),
    user: CurrentUser = Depends(rate_limit),
    transcriber: Transcriber = Depends(get_transcriber),
) -> TranscriptOut:
    """Speech → editable text. The audio is processed in memory and never stored.

    The client shows the transcript for correction, then sends it to /ai/message.
    """
    mime = (audio.content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_AUDIO:
        raise AppError("unsupported_audio", f"Unsupported audio type: {mime or 'unknown'}.", 415)
    mime = "audio/wav" if "wav" in mime else mime

    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise AppError("audio_too_large", "Recording is too long — keep it under 60 seconds.", 413)
    if len(data) < MIN_AUDIO_BYTES:
        raise AppError(
            "audio_too_short", "Recording is too short. Hold on and speak a bit longer.", 422
        )
    if mime == "audio/wav":
        if not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
            raise AppError("invalid_audio", "That file isn't a valid WAV recording.", 422)
        # Never send silence to the AI: transcribers can hallucinate text from nothing.
        try:
            silent = is_probably_silent(data)
        except InvalidWav as exc:
            raise AppError("invalid_audio", "That file isn't a valid WAV recording.", 422) from exc
        if silent:
            raise AppError(
                "no_speech",
                "I couldn't hear any speech. Try again a little closer to the mic.",
                422,
            )

    try:
        # Runs in a worker thread: the sync HTTP call must not block the event loop.
        result = await run_in_threadpool(transcriber.transcribe, data, mime)
    except NoSpeechError as exc:
        raise AppError("no_speech", NO_SPEECH_MESSAGE, 422) from exc
    except TranscriptionError as exc:
        raise AppError(
            "transcription_unavailable",
            "Voice recognition is busy right now. Try again, or type it instead.",
            503,
        ) from exc
    finally:
        del data  # drop the audio as soon as possible

    return TranscriptOut(text=result.text, language=result.language, provider=result.provider)


@router.post("/budget", response_model=AIBudgetOut)
def ai_budget(
    body: AIBudgetIn,
    user: CurrentUser = Depends(rate_limit),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> dict:
    """ "I have 20,000 this month, rent 5,000, save 3,000" → calculated budget DRAFT.

    The AI only extracts the numbers you said; the budget engine does all the maths.
    Nothing is saved until PUT /budgets/{month}.
    """
    month = parse_month(body.month)
    assert month is not None
    return plan_from_text(db, user.id, body.text, llm=llm, month=month)


@router.post("/ask", response_model=AskOut)
def ask(
    body: AskIn,
    user: CurrentUser = Depends(rate_limit),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> dict:
    """Answer a question from the user's own data using READ-ONLY tools.

    Returns the answer plus every tool call and its exact result, so the UI can show the
    real numbers next to the model's wording. Nothing is ever written.
    """
    return answer_question(
        db, user.id, body.text, llm=llm, history=[t.model_dump() for t in body.history]
    )
