"""Currency conversion helper."""
from __future__ import annotations

FX_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.0875,
    "KRW": 0.000725,
    "JPY": 0.00665,
}


def convert_amount(amount: float, src: str, dst: str) -> float:
    """Convert amount from src currency to dst currency.

    BUG 1b: Uses binary float arithmetic and banker's round() instead of
    Decimal(str(...)) with ROUND_HALF_UP (2 decimal places for USD/EUR, 0 for KRW/JPY).
    """
    if src not in FX_RATES_TO_USD or dst not in FX_RATES_TO_USD:
        raise ValueError(f"Unsupported currency pair: {src}->{dst}")
    if src == dst:
        return round(amount, 0 if dst in ("KRW", "JPY") else 2)
    usd = amount * FX_RATES_TO_USD[src]
    converted = usd / FX_RATES_TO_USD[dst]
    decimals = 0 if dst in ("KRW", "JPY") else 2
    return round(converted, decimals)
