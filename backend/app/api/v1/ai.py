from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai import service
from app.ai.llm_client import LLMClient
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.schemas.ai import AIMessageIn, AIMessageOut

router = APIRouter()


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
    return service.process_message(db, user.id, body.text, llm=llm, source=body.source)
