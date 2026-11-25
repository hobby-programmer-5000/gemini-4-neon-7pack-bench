"""Currency conversion helper using exact Decimal arithmetic."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

FX_RATES_TO_USD: dict[str, Decimal] = {
    "USD": Decimal("1.0"),
    "EUR": Decimal("1.0875"),
    "KRW": Decimal("0.000725"),
    "JPY": Decimal("0.00665"),
}

ZERO_DECIMAL_CURRENCIES = frozenset({"KRW", "JPY"})


def quantize_amount(amount: Decimal | int | float | str, currency: str) -> Decimal:
    """Round amount to currency minor units using exact Decimal ROUND_HALF_UP."""
    dec_amount = Decimal(str(amount))
    quantizer = Decimal("1") if currency in ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
    return dec_amount.quantize(quantizer, rounding=ROUND_HALF_UP)


def convert_amount(amount: Decimal | int | float | str, src: str, dst: str) -> Decimal:
    """Convert amount from src currency to dst currency using Decimal and ROUND_HALF_UP.

    Uses 2 decimal places for USD/EUR and 0 decimal places for KRW/JPY.
    """
    if src not in FX_RATES_TO_USD or dst not in FX_RATES_TO_USD:
        raise ValueError(f"Unsupported currency pair: {src}->{dst}")
    dec_amount = Decimal(str(amount))
    if src == dst:
        return quantize_amount(dec_amount, dst)
    usd = dec_amount * FX_RATES_TO_USD[src]
    converted = usd / FX_RATES_TO_USD[dst]
    return quantize_amount(converted, dst)
