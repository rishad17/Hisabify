"""First-login setup: create the profile, default categories and a Cash wallet.

Called on every GET /me, but only does work the very first time. It is safe against
two requests racing on first login (e.g. two browser tabs): the profile insert uses
ON CONFLICT DO NOTHING, and only the request that actually inserted it seeds defaults.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Category, Profile, Wallet


@dataclass(frozen=True)
class DefaultCategory:
    name: str
    name_bn: str
    kind: str
    icon: str
    is_essential: bool = False


# Icons are lucide-react icon names, rendered by the frontend.
DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    # Expenses
    DefaultCategory("Food & Drinks", "খাবার ও পানীয়", "expense", "utensils"),
    DefaultCategory("Groceries", "বাজার", "expense", "shopping-basket", is_essential=True),
    DefaultCategory("Transport", "যাতায়াত", "expense", "bus", is_essential=True),
    DefaultCategory("Rent", "বাসা ভাড়া", "expense", "house", is_essential=True),
    DefaultCategory("Bills & Utilities", "বিল", "expense", "receipt", is_essential=True),
    DefaultCategory("Mobile & Internet", "মোবাইল ও ইন্টারনেট", "expense", "smartphone"),
    DefaultCategory("Education", "শিক্ষা", "expense", "graduation-cap", is_essential=True),
    DefaultCategory("Healthcare", "স্বাস্থ্য", "expense", "heart-pulse", is_essential=True),
    DefaultCategory("Shopping", "কেনাকাটা", "expense", "shopping-bag"),
    DefaultCategory("Entertainment", "বিনোদন", "expense", "clapperboard"),
    DefaultCategory("Family & Gifts", "পরিবার ও উপহার", "expense", "gift"),
    DefaultCategory("Miscellaneous", "অন্যান্য", "expense", "ellipsis"),
    # Income
    DefaultCategory("Salary", "বেতন", "income", "briefcase"),
    DefaultCategory("Allowance", "হাতখরচ", "income", "hand-coins"),
    DefaultCategory("Tuition", "টিউশনি", "income", "book-open"),
    DefaultCategory("Freelance", "ফ্রিল্যান্স", "income", "laptop"),
    DefaultCategory("Gift Received", "উপহার প্রাপ্তি", "income", "gift"),
    DefaultCategory("Refund", "ফেরত", "income", "rotate-ccw"),
    DefaultCategory("Other Income", "অন্যান্য আয়", "income", "plus-circle"),
)

DEFAULT_WALLET_NAME = "Cash"


def ensure_profile(db: Session, user_id: uuid.UUID) -> tuple[Profile, bool]:
    """Return (profile, created). Commits if anything was created."""
    inserted_id = db.execute(
        pg_insert(Profile)
        .values(id=user_id)
        .on_conflict_do_nothing(index_elements=[Profile.id])
        .returning(Profile.id)
    ).scalar_one_or_none()

    created = inserted_id is not None
    if created:
        db.execute(
            insert(Category),
            [
                {
                    "user_id": user_id,
                    "name": c.name,
                    "name_bn": c.name_bn,
                    "kind": c.kind,
                    "icon": c.icon,
                    "is_essential": c.is_essential,
                }
                for c in DEFAULT_CATEGORIES
            ],
        )
        db.add(Wallet(user_id=user_id, name=DEFAULT_WALLET_NAME, type="cash", is_default=True))
        db.commit()

    profile = db.scalars(select(Profile).where(Profile.id == user_id)).one()
    return profile, created
