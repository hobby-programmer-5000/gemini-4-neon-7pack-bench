"""Core transfer engine."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
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
        amount: Decimal | int | float | str,
        created_at: datetime | None = None,
        memo: str = "",
        idempotency_key: str | None = None,
    ) -> LedgerEntry:
        """Transfer amount in source account currency to destination account atomically."""
        if from_id == to_id:
            raise ValueError("Self-transfer is not permitted")

        dec_amount = Decimal(str(amount))
        if not dec_amount.is_finite() or dec_amount <= Decimal("0"):
            raise ValueError("Transfer amount must be positive")

        def _tx() -> LedgerEntry:
            if idempotency_key is not None:
                existing = self.store.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing

            src = self.store.get_account(from_id)
            dst = self.store.get_account(to_id)

            source_amount = convert_amount(dec_amount, src.currency, src.currency)
            if source_amount <= Decimal("0"):
                raise ValueError("Transfer amount must be positive")

            if src.balance < source_amount:
                raise InsufficientFundsError(f"Balance {src.balance} < {source_amount}")

            src.balance -= source_amount
            target_amount = convert_amount(source_amount, src.currency, dst.currency)
            dst.balance += target_amount

            ts = created_at if created_at is not None else datetime.now(timezone.utc)
            entry = LedgerEntry(
                entry_id=str(uuid.uuid4()),
                from_account=from_id,
                to_account=to_id,
                amount_source=source_amount,
                amount_target=target_amount,
                source_currency=src.currency,
                target_currency=dst.currency,
                created_at=ts,
                memo=memo,
                idempotency_key=idempotency_key,
            )
            self.store.record_entry(entry)
            return entry

        return self.store.run_atomic(_tx)
