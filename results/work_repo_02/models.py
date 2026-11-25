"""Data models for the multi-currency settlement ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Account:
    account_id: str
    currency: str
    balance: Decimal

    def __post_init__(self) -> None:
        self.balance = Decimal(str(self.balance))


@dataclass
class LedgerEntry:
    entry_id: str
    from_account: str
    to_account: str
    amount_source: Decimal
    amount_target: Decimal
    source_currency: str
    target_currency: str
    created_at: datetime
    memo: str = ""
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        self.amount_source = Decimal(str(self.amount_source))
        self.amount_target = Decimal(str(self.amount_target))
