"""Shared field types for request/response schemas."""

from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _parse_money(value: object) -> object:
    """Accept "1,250.50", "১২৫০", 1250 → Decimal. Floats are rejected on purpose:
    a float like 0.1 is already inexact before it reaches us."""
    if isinstance(value, float):
        raise ValueError('send money as a string (e.g. "125.50"), not a float')
    if isinstance(value, str):
        cleaned = value.translate(_BANGLA_DIGITS).replace(",", "").replace("৳", "").strip()
        return cleaned
    return value


# Money in API payloads:
#   * input: string or integer, max 2 decimal places, Bangla digits allowed
#   * output: always a string with exactly 2 decimals, e.g. "1250.00"
Money = Annotated[
    Decimal,
    BeforeValidator(_parse_money),
    Field(max_digits=14, decimal_places=2),
    PlainSerializer(lambda d: f"{d:.2f}", return_type=str, when_used="json"),
]
PositiveMoney = Annotated[Money, Field(gt=0)]
NonNegativeMoney = Annotated[Money, Field(ge=0)]
