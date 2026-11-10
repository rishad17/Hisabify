"""Deterministic clean-up of user text BEFORE it reaches the LLM.

Small, predictable transformations here make the model's job easier and cheaper:
Bangla digits become ASCII (১০০ → 100), whitespace is collapsed, and length is capped.
We deliberately do NOT translate words — the LLM handles Banglish/Bangla meaning.
"""

import re
import unicodedata

MAX_INPUT_CHARS = 500

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")


def normalize_user_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)  # consistent Bangla character composition
    text = text.translate(_BANGLA_DIGITS)
    text = _CONTROL.sub(" ", text)
    text = text.replace("৳", " taka ")
    text = " ".join(text.split())
    return text[:MAX_INPUT_CHARS]
