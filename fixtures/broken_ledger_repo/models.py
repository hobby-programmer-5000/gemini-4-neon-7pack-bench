"""Data models for the multi-currency settlement ledger."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Account:
    account_id: str
    currency: str
    # BUG 1a: Storing balances as binary float causes penny drift!
    balance: float


@dataclass
class LedgerEntry:
    entry_id: str
    from_account: str
    to_account: str
    amount_source: float
    amount_target: float
    source_currency: str
    target_currency: str
    created_at: datetime
    # BUG 3a: Missing idempotency_key propagation across models/engine/storage/api
    memo: str = ""
