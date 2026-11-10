"""Check that every ৳ amount in the assistant's answer actually came from the tools.

Why: in live testing the model called the right tool (total ৳11,990.50) and then wrote
"৳11,900.50" — a copying slip. The data cards would still be right, but the answer text
must not quietly contain a wrong number. So, deterministically:

  * collect every number the tools returned
  * also allow sums/differences of two tool numbers (the prompt lets the model show
    simple arithmetic like "৳18,470 + ৳13,360 = ৳31,830")
  * any ৳ amount in the answer that isn't in that set is "unverified"
"""

import itertools
import re
from decimal import Decimal, InvalidOperation
from typing import Any

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_AMOUNT_IN_TEXT = re.compile(r"৳\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
_NUMBER_STR = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
MAX_NUMBERS = 300  # keeps the pairwise check cheap


def _to_decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def amounts_in_answer(answer: str) -> list[tuple[str, Decimal]]:
    found = []
    for match in _AMOUNT_IN_TEXT.finditer(answer.translate(_BANGLA_DIGITS)):
        value = _to_decimal(match.group(1))
        if value is not None:
            found.append((match.group(0).strip(), value))
    return found


def numbers_in(data: Any, out: set[Decimal] | None = None) -> set[Decimal]:
    out = out if out is not None else set()
    if isinstance(data, dict):
        for v in data.values():
            numbers_in(v, out)
    elif isinstance(data, list):
        for v in data:
            numbers_in(v, out)
    elif isinstance(data, bool):
        pass
    elif isinstance(data, (int, float)):
        out.add(Decimal(str(data)).quantize(Decimal("0.01")))
    elif isinstance(data, str) and _NUMBER_STR.match(data.strip()):
        value = _to_decimal(data.strip())
        if value is not None:
            out.add(value)
    return out


def unverified_amounts(answer: str, tool_results: list[dict]) -> list[str]:
    """৳ amounts in `answer` that can't be traced to the tool results."""
    mentioned = amounts_in_answer(answer)
    if not mentioned:
        return []
    known: set[Decimal] = set()
    for result in tool_results:
        numbers_in(result, known)
    known = {abs(n) for n in known}
    base = sorted(known)[:MAX_NUMBERS]
    derived = set(base)
    for a, b in itertools.combinations(base, 2):
        derived.add(a + b)
        derived.add(abs(a - b))
    return [text for text, value in mentioned if value not in derived]
