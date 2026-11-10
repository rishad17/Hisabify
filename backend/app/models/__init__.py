"""Importing this package registers every table on Base.metadata (Alembic needs that)."""

from app.models.ai_interaction import AIInteraction
from app.models.budget import Budget, BudgetAdjustment, BudgetItem
from app.models.category import Category
from app.models.commitment import ExpectedIncome, RecurringBill, SavingsGoal
from app.models.profile import Profile
from app.models.transaction import Transaction
from app.models.wallet import Wallet

__all__ = [
    "AIInteraction",
    "Budget",
    "BudgetAdjustment",
    "BudgetItem",
    "Category",
    "ExpectedIncome",
    "Profile",
    "RecurringBill",
    "SavingsGoal",
    "Transaction",
    "Wallet",
]
