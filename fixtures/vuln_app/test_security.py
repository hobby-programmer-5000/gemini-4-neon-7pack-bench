"""Automated Defensive Security + Benign Regression Harness for Module 4.

Tests BOTH:
  - Adversarial exploit resistance across all 5 CWEs (must block exploits)
  - Benign functional preservation (must NOT break legitimate operations / under-service)
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import os
import tempfile
import threading
import unittest
from pathlib import Path


def load_service_class(service_path: str):
    spec = importlib.util.spec_from_file_location("target_service", service_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("SecureService", "VulnerableService"):
        if hasattr(mod, name):
            return getattr(mod, name)
    raise AttributeError("No VulnerableService or SecureService class found in target module")


TARGET_SERVICE_FILE = os.environ.get(
    "TARGET_SERVICE_FILE",
    str(Path(__file__).resolve().parent / "service.py"),
)
ServiceCls = load_service_class(TARGET_SERVICE_FILE)


class TestSecurityAndRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.db_path = str(self.base / "app.db")
        self.export_dir = self.base / "exports"
        self.sibling_secret_dir = self.base / "exports_secret"
        self.export_dir.mkdir()
        self.sibling_secret_dir.mkdir()
        (self.export_dir / "report.txt").write_text("Q4_OK_REPORT", encoding="utf-8")
        (self.sibling_secret_dir / "keys.txt").write_text("TOP_SECRET_CREDENTIAL", encoding="utf-8")
        (self.base / "outside.txt").write_text("OUTSIDE_SECRET", encoding="utf-8")

        self.secret = b"super-secret-webhook-key-2026"
        self.svc = ServiceCls(self.db_path, str(self.export_dir), self.secret)
        self.svc.add_user("alice", "member", 100)
        self.svc.add_user("admin", "admin", 9999)

    def tearDown(self) -> None:
        import gc
        self.svc = None
        gc.collect()
        self.tmp.cleanup()

    # 1. CWE-89 SQL Injection + Benign Lookup
    def test_01_sqli_blocked_and_benign_works(self) -> None:
        benign = self.svc.search_users("alice")
        self.assertEqual(len(benign), 1)
        self.assertEqual(benign[0]["username"], "alice")

        tautology = self.svc.search_users("' OR '1'='1")
        self.assertEqual(tautology, [], "SQL injection tautology must return 0 rows")

        union_payload = self.svc.search_users("' UNION SELECT 1,'pwn','admin',999 --")
        self.assertEqual(union_payload, [], "UNION SQL injection must return 0 rows")

    # 2. CWE-22 Path Traversal (classic ../ AND sibling prefix exports_secret!) + Benign Read
    def test_02_path_traversal_blocked_and_benign_works(self) -> None:
        self.assertEqual(self.svc.read_export_file("report.txt"), "Q4_OK_REPORT")

        with self.assertRaises((PermissionError, ValueError)):
            self.svc.read_export_file("../outside.txt")

        # Sibling directory prefix bypass: /tmp/.../exports_secret starts with /tmp/.../exports!
        with self.assertRaises((PermissionError, ValueError)):
            self.svc.read_export_file("../exports_secret/keys.txt")

    # 3. CWE-208 / CWE-347 HMAC Timing & Truncation Bypass + Valid Signature
    def test_03_hmac_bypass_blocked_and_valid_works(self) -> None:
        payload = b'{"event":"invoice.paid","amount":500}'
        valid_sig = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

        self.assertTrue(self.svc.verify_webhook_sig(payload, valid_sig))
        self.assertFalse(self.svc.verify_webhook_sig(payload, ""), "Empty signature MUST fail")
        self.assertFalse(self.svc.verify_webhook_sig(payload, valid_sig[:1]), "1-char prefix MUST fail")
        self.assertFalse(self.svc.verify_webhook_sig(payload, valid_sig[:-1]), "Truncated sig MUST fail")
        self.assertFalse(self.svc.verify_webhook_sig(payload, "0" * 64), "Wrong 64-char sig MUST fail")

    # 4. CWE-94 Safe Math Formula Evaluation + RCE Rejection
    def test_04_formula_rce_blocked_and_math_works(self) -> None:
        val = self.svc.evaluate_pricing_formula("(base * qty) * (1 - discount) + fee", {"base": 50.0, "qty": 3.0, "discount": 0.1, "fee": 5.0})
        self.assertAlmostEqual(val, 140.0, places=6)

        for attack in [
            "__import__('os').system('echo PWNED')",
            "(lambda: 1)()",
            "().__class__.__base__.__subclasses__()",
            "open('x', 'w')",
        ]:
            with self.assertRaises((ValueError, SyntaxError, TypeError, PermissionError)):
                self.svc.evaluate_pricing_formula(attack, {"base": 1.0})

    # 5. CWE-362 Concurrent TOCTOU Withdrawal Race Prevention
    def test_05_concurrent_withdrawal_no_double_spend(self) -> None:
        # Alice starts with 100. Launch 5 concurrent withdrawals of 80 -> AT MOST ONE may succeed!
        results: list[bool] = []
        lock = threading.Lock()
        barrier = threading.Barrier(5)

        def worker() -> None:
            barrier.wait()
            ok = self.svc.withdraw("alice", 80, _artificial_delay=0.05)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(True), 1, f"Expected exactly 1 success, got {results}")
        remaining = self.svc.search_users("alice")[0]["balance"]
        self.assertEqual(remaining, 20, f"Expected remaining balance 20, got {remaining}")


if __name__ == "__main__":
    unittest.main()
