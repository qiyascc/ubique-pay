"""Card tokenization helpers.

The PAN never touches our database. In production this is the job of a PCI card
vault (Checkout.com Frames, Visa/Mastercard tokenization, ...); here we derive
the brand + last 4 and mint a placeholder token so the flow is complete and
PCI-safe end to end.
"""

import uuid


def card_brand(digits: str) -> str:
    if digits.startswith("4"):
        return "Visa"
    if digits[:2] in {"51", "52", "53", "54", "55"}:
        return "Mastercard"
    if len(digits) >= 4 and 2221 <= int(digits[:4]) <= 2720:
        return "Mastercard"
    if digits[:2] in {"34", "37"}:
        return "Amex"
    return "Card"


def luhn_valid(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def tokenize_card(number: str):
    """Return (token, last4, brand). Raises ValueError on an invalid number."""
    digits = "".join(c for c in str(number) if c.isdigit())
    if not (12 <= len(digits) <= 19 and luhn_valid(digits)):
        raise ValueError("Invalid card number.")
    return f"rct_{uuid.uuid4().hex[:16]}", digits[-4:], card_brand(digits)
