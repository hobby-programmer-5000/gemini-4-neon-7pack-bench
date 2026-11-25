"""Core transfer engine."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from currency import convert_amount
from models import LedgerEntry
from storage import InsufficientFundsError, LedgerStore


class LedgerEngine:
    def __init__(self, store: LedgerStore) -> None:
        self.store = store

    def transfer(
        self,
        from_id: str,
        to_id: str,
        amount: float,
        created_at: datetime | None = None,
        memo: str = "",
    ) -> LedgerEntry:
        """Transfer amount in source account currency to destination account.

        BUG 1c: Float arithmetic drift & negative/zero amount not rejected cleanly.
        BUG 3b: Does not accept or enforce `idempotency_key`.
        """
        if from_id == to_id:
            raise ValueError("Self-transfer is not permitted")

        def _tx() -> LedgerEntry:
            src = self.store.get_account(from_id)
            dst = self.store.get_account(to_id)
            if amount <= 0:
                raise ValueError("Transfer amount must be positive")
            # Debit first so if destination fails later, rollback MUST restore src!
            if src.balance < amount:
                raise InsufficientFundsError(f"Balance {src.balance} < {amount}")
            src.balance -= amount
            target_amount = convert_amount(amount, src.currency, dst.currency)
            dst.balance += target_amount
            ts = created_at or datetime.now(timezone.utc)
            entry = LedgerEntry(
                entry_id=str(uuid.uuid4()),
                from_account=from_id,
                to_account=to_id,
                amount_source=amount,
                amount_target=target_amount,
                source_currency=src.currency,
                target_currency=dst.currency,
                created_at=ts,
                memo=memo,
            )
            self.store.entries.append(entry)
            return entry

        return self.store.run_atomic(_tx)
