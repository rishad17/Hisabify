from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models import Category, Wallet
from app.schemas.me import MeOut, ProfileOut, ProfileUpdate
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
