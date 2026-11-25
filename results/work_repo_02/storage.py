"""In-memory transactional store for accounts and entries."""
from __future__ import annotations

import copy
from typing import Callable, TypeVar

from models import Account, LedgerEntry

T = TypeVar("T")


class InsufficientFundsError(Exception):
    pass


class LedgerStore:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.entries: list[LedgerEntry] = []
        self.idempotency_index: dict[str, LedgerEntry] = {}

    def add_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Account:
        if account_id not in self.accounts:
            raise KeyError(f"Unknown account: {account_id}")
        return self.accounts[account_id]

    def get_by_idempotency_key(self, idempotency_key: str) -> LedgerEntry | None:
        return self.idempotency_index.get(idempotency_key)

    def record_entry(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)
        if entry.idempotency_key is not None:
            self.idempotency_index[entry.idempotency_key] = entry

    def run_atomic(self, fn: Callable[[], T]) -> T:
        """Execute fn atomically with full state rollback and exception propagation on failure."""
        snapshot_accounts = copy.deepcopy(self.accounts)
        snapshot_entries = copy.deepcopy(self.entries)
        snapshot_idem = copy.deepcopy(self.idempotency_index)
        try:
            return fn()
        except BaseException:
            self.accounts = snapshot_accounts
            self.entries = snapshot_entries
            self.idempotency_index = snapshot_idem
            raise
