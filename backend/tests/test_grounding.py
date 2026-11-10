"""Grounding check for assistant answers — pure, no DB."""


def test_grounding_unit():
    from app.ai.grounding import unverified_amounts

    results = [{"total": "11990.50", "wallets": [{"balance": "3250.00"}, {"balance": "8740.50"}]}]
    assert unverified_amounts("You have ৳11,990.50 (Cash ৳3,250).", results) == []
    assert unverified_amounts("You have ৳11,900.50.", results) == ["৳11,900.50"]
    # Sums/differences of two tool numbers are allowed (shown arithmetic).
    assert unverified_amounts("৳8,740.50 − ৳3,250 = ৳5,490.50", results) == []
    assert unverified_amounts("আপনার আছে ৳১১,৯৯০.৫০", results) == []  # Bangla digits
    assert unverified_amounts("No amounts here.", results) == []
