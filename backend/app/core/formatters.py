from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union


def format_crypto_price(value: Union[float, int, Decimal, str, None]) -> str:
    """Formats crypto prices without scientific notation or excessive trailing zeros."""
    if value is None or value == "":
        return "—"

    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return "—"

    if not dec.is_finite():
        return "—"
    if dec == 0:
        return "0"

    quantum = Decimal("0.0001") if abs(dec) >= 1 else Decimal("0.00000001")
    rounded = dec.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        return "0"

    text = f"{rounded:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
