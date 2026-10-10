from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def as_money(value) -> Decimal:
    if value is None:
        return ZERO
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_inr(value) -> str:
    amount = as_money(value)
    negative = amount < 0
    amount = abs(amount)
    rupees, paise = f"{amount:.2f}".split(".")
    if len(rupees) <= 3:
        grouped = rupees
    else:
        last3 = rupees[-3:]
        rest = rupees[:-3]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(reversed(parts)) + "," + last3
    formatted = f"₹{grouped}.{paise}"
    return f"-{formatted}" if negative else formatted
