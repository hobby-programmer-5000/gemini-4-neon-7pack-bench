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

    def run_atomic(self, fn: Callable[[], T]) -> T | None:
        """Execute fn atomically with rollback on failure.

        BUG 2: `return result` inside `finally` swallows EVERY exception and skips rollback!
        """
        snapshot_accounts = copy.deepcopy(self.accounts)
        snapshot_entries = copy.deepcopy(self.entries)
        snapshot_idem = copy.deepcopy(self.idempotency_index)
        result = None
        try:
            result = fn()
        except Exception:
            self.accounts = snapshot_accounts
            self.entries = snapshot_entries
            self.idempotency_index = snapshot_idem
            raise
        finally:
            return result
