from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
USDT_UNIT = Decimal("0.000001")  # USDT has 6 decimals


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def usdt(value) -> Decimal:
    return Decimal(str(value)).quantize(USDT_UNIT, rounding=ROUND_HALF_UP)
