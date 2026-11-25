"""Authoritative verification test suite for broken_ledger_repo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from api import LedgerAPI
from currency import convert_amount
from storage import InsufficientFundsError


class TestMultiCurrencyLedger(unittest.TestCase):
    def test_01_decimal_precision_no_float_drift(self) -> None:
        api = LedgerAPI()
        api.create_account("alice", "USD", "1.00")
        api.create_account("bob", "USD", "0.00")
        for _ in range(10):
            api.post_transfer("alice", "bob", "0.10")
        self.assertEqual(Decimal(api.get_balance("alice")), Decimal("0.00"))
        self.assertEqual(Decimal(api.get_balance("bob")), Decimal("1.00"))

    def test_02_round_half_up_fx_conversion(self) -> None:
        # 1.005 USD -> USD must round HALF_UP to 1.01, not banker's 1.00
        self.assertEqual(Decimal(str(convert_amount(Decimal("1.005"), "USD", "USD"))), Decimal("1.01"))
        # 10.00 USD -> KRW: 10 / 0.000725 = 13793.1034... -> 13793 (0 decimal places)
        self.assertEqual(Decimal(str(convert_amount(Decimal("10.00"), "USD", "KRW"))), Decimal("13793"))
        # 1.00 EUR -> USD: 1.00 * 1.0875 = 1.0875 -> 1.09 (HALF_UP)
        self.assertEqual(Decimal(str(convert_amount(Decimal("1.00"), "EUR", "USD"))), Decimal("1.09"))

    def test_03_atomic_rollback_and_exception_propagation(self) -> None:
        api = LedgerAPI()
        api.create_account("alice", "USD", "50.00")
        api.create_account("bob", "USD", "10.00")
        # Insufficient funds MUST raise InsufficientFundsError, NOT return None!
        with self.assertRaises(InsufficientFundsError):
            api.post_transfer("alice", "bob", "99.00")
        self.assertEqual(Decimal(api.get_balance("alice")), Decimal("50.00"))
        self.assertEqual(Decimal(api.get_balance("bob")), Decimal("10.00"))

        # Unknown destination MUST raise KeyError and NOT mutate source balance
        with self.assertRaises(KeyError):
            api.post_transfer("alice", "ghost", "10.00")
        self.assertEqual(Decimal(api.get_balance("alice")), Decimal("50.00"))

    def test_04_idempotency_key_deduplication(self) -> None:
        api = LedgerAPI()
        api.create_account("alice", "USD", "100.00")
        api.create_account("bob", "USD", "0.00")
        r1 = api.post_transfer("alice", "bob", "25.00", idempotency_key="tx-idem-001")
        r2 = api.post_transfer("alice", "bob", "25.00", idempotency_key="tx-idem-001")
        self.assertEqual(r1["entry_id"], r2["entry_id"])
        self.assertEqual(r1["idempotency_key"], "tx-idem-001")
        self.assertEqual(Decimal(api.get_balance("alice")), Decimal("75.00"))
        self.assertEqual(Decimal(api.get_balance("bob")), Decimal("25.00"))
        self.assertEqual(len(api.store.entries), 1)

    def test_05_utc_daily_reporting_across_timezones(self) -> None:
        api = LedgerAPI()
        api.create_account("alice", "USD", "100.00")
        api.create_account("bob", "USD", "0.00")
        kst = timezone(timedelta(hours=9))
        # 2026-11-25 01:30:00+09:00 is 2026-11-24 16:30:00Z!
        ts_kst = datetime(2026, 11, 25, 1, 30, 0, tzinfo=kst)
        ts_utc = datetime(2026, 11, 24, 23, 0, 0, tzinfo=timezone.utc)
        api.post_transfer("alice", "bob", "12.35", created_at=ts_kst)
        api.post_transfer("alice", "bob", "7.65", created_at=ts_utc)
        report = api.get_daily_report()
        self.assertIn("2026-11-24", report)
        self.assertNotIn("2026-11-25", report)
        self.assertEqual(Decimal(report["2026-11-24"]["USD"]), Decimal("20.00"))


if __name__ == "__main__":
    unittest.main()
