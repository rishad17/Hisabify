from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import CurrentUser, get_current_user
from app.models import Category, Wallet
from app.schemas.me import MeOut, ProfileOut, ProfileUpdate
from app.services import account
from app.services.onboarding import ensure_profile

router = APIRouter()


def _build_me(db: Session, user: CurrentUser, profile, is_new: bool) -> MeOut:
    default_wallet = db.scalar(
        select(Wallet.name).where(
            Wallet.user_id == user.id, Wallet.is_default, Wallet.archived_at.is_(None)
        )
    )
    category_count = db.scalar(
        select(func.count())
        .select_from(Category)
        .where(Category.user_id == user.id, Category.archived_at.is_(None))
    )
    return MeOut(
        profile=ProfileOut.model_validate(profile),
        email=user.email,
        default_wallet_name=default_wallet,
        category_count=category_count or 0,
        is_new_user=is_new,
    )


@router.get("", response_model=MeOut)
def get_me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    """Current user's profile. The first call after sign-up also sets up the account."""
    profile, created = ensure_profile(db, user.id)
    return _build_me(db, user, profile, created)


@router.patch("", response_model=MeOut)
def update_me(
    body: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    profile, _ = ensure_profile(db, user.id)
    # exclude_unset: only fields the client actually sent are applied.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    return _build_me(db, user, profile, False)


# ------------------------------------------------------------------ your data


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The user must type DELETE — protects against accidental or forged clicks.
    confirm: Literal["DELETE"]


@router.get("/export.csv")
def export_csv(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    """All non-deleted transactions as CSV (UTF-8 with BOM so Excel shows Bangla)."""
    return StreamingResponse(
        account.export_transactions_csv(db, user.id),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="hisabify-transactions.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("/data", status_code=204)
def delete_my_data(
    body: ConfirmIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    """Permanently delete ALL financial data. The account starts fresh on next load."""
    account.wipe_user_data(db, user.id)
    return Response(status_code=204)


def require_account_deletion(request: Request) -> tuple[str, str]:
    """Checked BEFORE touching the database: deleting an account needs the admin key."""
    settings = request.app.state.settings
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise AppError(
            "account_deletion_not_configured",
            "Account deletion isn't set up on this server yet. You can still delete all your data.",
            503,
        )
    return settings.supabase_url, settings.supabase_service_role_key


@router.delete("", status_code=204)
def delete_my_account(
    body: ConfirmIn,
    admin: tuple[str, str] = Depends(require_account_deletion),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete all data AND the sign-in account."""
    supabase_url, service_key = admin
    # Remove the login first: if that fails, the data is still intact and the user can retry.
    account.delete_auth_user(supabase_url, service_key, user.id)
    account.wipe_user_data(db, user.id)
    return Response(status_code=204)
