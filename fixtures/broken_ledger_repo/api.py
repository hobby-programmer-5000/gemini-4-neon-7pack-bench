"""Public service facade over engine and reporting."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from engine import LedgerEngine
from models import Account
from reporting import daily_volume_by_source_currency
from storage import LedgerStore


class LedgerAPI:
    def __init__(self) -> None:
        self.store = LedgerStore()
        self.engine = LedgerEngine(self.store)

    def create_account(self, account_id: str, currency: str, initial_balance: Any) -> Account:
        acc = Account(account_id=account_id, currency=currency, balance=initial_balance)
        self.store.add_account(acc)
        return acc

    def post_transfer(
        self,
        from_id: str,
        to_id: str,
        amount: Any,
        created_at: datetime | None = None,
        memo: str = "",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # BUG 3c: Ignores idempotency_key completely instead of forwarding to engine!
        entry = self.engine.transfer(
            from_id=from_id,
            to_id=to_id,
            amount=amount,
            created_at=created_at,
            memo=memo,
        )
        return {
            "entry_id": entry.entry_id,
            "from_account": entry.from_account,
            "to_account": entry.to_account,
            "amount_source": str(entry.amount_source),
            "amount_target": str(entry.amount_target),
            "source_currency": entry.source_currency,
            "target_currency": entry.target_currency,
            "idempotency_key": getattr(entry, "idempotency_key", None),
        }

    def get_balance(self, account_id: str) -> str:
        return str(self.store.get_account(account_id).balance)

    def get_daily_report(self) -> dict[str, dict[str, str]]:
        raw = daily_volume_by_source_currency(self.store)
        return {day: {cur: str(val) for cur, val in cmap.items()} for day, cmap in raw.items()}
