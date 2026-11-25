"""Intentionally vulnerable local sandbox service for Defensive Root-Cause Patching Benchmark.

Contains 5 real CWE classes for local unittest verification ONLY:
  1. CWE-89: SQL Injection in search_users()
  2. CWE-22: Path Traversal (including sibling-prefix bypass) in read_export_file()
  3. CWE-208 / CWE-347: Weak/timing-leaky HMAC + prefix-truncation bug in verify_webhook_sig()
  4. CWE-94 / CWE-502: Arbitrary code execution via eval() in evaluate_pricing_formula()
  5. CWE-362: TOCTOU race condition in withdraw()
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


class VulnerableService:
    def __init__(self, db_path: str, export_root: str, webhook_secret: bytes) -> None:
        self.db_path = db_path
        self.export_root = os.path.abspath(export_root)
        self.webhook_secret = webhook_secret
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def add_user(self, username: str, role: str, balance: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(username, role, balance) VALUES (?, ?, ?)",
                (username, role, balance),
            )
            conn.commit()

    # VULN 1 (CWE-89): Direct string interpolation in SQL query
    def search_users(self, username_query: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            sql = f"SELECT id, username, role, balance FROM users WHERE username = '{username_query}'"
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    # VULN 2 (CWE-22): Naive string join + naive startswith prefix bug
    def read_export_file(self, filename: str) -> str:
        candidate = os.path.abspath(os.path.join(self.export_root, filename))
        if not candidate.startswith(self.export_root):
            raise PermissionError("Path outside export root")
        return Path(candidate).read_text(encoding="utf-8")

    # VULN 3 (CWE-208 / CWE-347): Non-constant-time prefix comparison allowing empty/short signature bypass
    def verify_webhook_sig(self, payload: bytes, provided_sig: str) -> bool:
        expected = hmac.new(self.webhook_secret, payload, hashlib.sha256).hexdigest()
        # Bug: zip() stops at shortest iterable -> empty string "" or 1-char prefix passes!
        for a, b in zip(expected, provided_sig):
            if a != b:
                return False
        return True

    # VULN 4 (CWE-94): Direct eval() on untrusted arithmetic formula
    def evaluate_pricing_formula(self, formula: str, variables: dict[str, float]) -> float:
        return float(eval(formula, {"__builtins__": __builtins__}, variables))

    # VULN 5 (CWE-362): Non-atomic check-then-act balance withdrawal (TOCTOU race)
    def withdraw(self, username: str, amount: int, _artificial_delay: float = 0.0) -> bool:
        if amount <= 0:
            raise ValueError("amount must be positive")
        conn = self._connect()
        try:
            row = conn.execute("SELECT balance FROM users WHERE username = ?", (username,)).fetchone()
            if row is None:
                raise KeyError(username)
            current = int(row["balance"])
            if current < amount:
                return False
            if _artificial_delay > 0:
                time.sleep(_artificial_delay)
            conn.execute(
                "UPDATE users SET balance = ? WHERE username = ?",
                (current - amount, username),
            )
            conn.commit()
            return True
        finally:
            conn.close()
