from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, get_current_user
from app.models import Category
from app.schemas.category import CategoryOut

router = APIRouter()


@router.get("", response_model=list[CategoryOut])
def list_categories(
    kind: Literal["expense", "income"] | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Category]:
    # Every query filters on the verified user id — this is our row-level access control.
    stmt = select(Category).where(Category.user_id == user.id, Category.archived_at.is_(None))
    if kind:
        stmt = stmt.where(Category.kind == kind)
    # "expense" sorts before "income" alphabetically, so expense categories come first.
    return list(db.scalars(stmt.order_by(Category.kind, Category.name)))
