"""Remediated local sandbox service with root-cause security fixes."""
from __future__ import annotations

import ast
import hashlib
import hmac
import operator
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_HEX_CHARS = frozenset("0123456789abcdefABCDEF")


class VulnerableService:
    def __init__(self, db_path: str, export_root: str, webhook_secret: bytes) -> None:
        self.db_path = db_path
        self.export_root = os.path.abspath(export_root)
        self.webhook_secret = webhook_secret
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
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

    def search_users(self, username_query: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, balance FROM users WHERE username = ?",
                (username_query,),
            ).fetchall()
            return [dict(r) for r in rows]

    def read_export_file(self, filename: str) -> str:
        if not isinstance(filename, str) or "\x00" in filename:
            raise PermissionError("Invalid filename")
        root = Path(self.export_root).resolve()
        candidate = (root / filename).resolve()
        if not candidate.is_relative_to(root) or candidate == root:
            raise PermissionError("Path outside export root")
        return candidate.read_text(encoding="utf-8")

    def verify_webhook_sig(self, payload: bytes, provided_sig: str) -> bool:
        if not isinstance(provided_sig, str):
            return False
        expected = hmac.new(self.webhook_secret, payload, hashlib.sha256).hexdigest()
        if len(provided_sig) != len(expected) or not all(c in _HEX_CHARS for c in provided_sig):
            return False
        return hmac.compare_digest(expected, provided_sig.lower())

    def evaluate_pricing_formula(self, formula: str, variables: dict[str, float]) -> float:
        if not isinstance(formula, str):
            raise ValueError("Formula must be a string")
        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Invalid formula syntax") from exc

        def _eval_node(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                    raise ValueError("Only numeric constants are allowed")
                return float(node.value)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in variables:
                    raise ValueError(f"Unknown variable: {node.id}")
                val = variables[node.id]
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    raise ValueError(f"Variable {node.id} must be numeric")
                return float(val)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
                return float(_UNARY_OPS[type(node.op)](_eval_node(node.operand)))
            if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                return float(_BIN_OPS[type(node.op)](left, right))
            raise ValueError(f"Disallowed expression node: {type(node).__name__}")

        return float(_eval_node(tree))

    def withdraw(self, username: str, amount: int, _artificial_delay: float = 0.0) -> bool:
        if amount <= 0:
            raise ValueError("amount must be positive")
        conn = self._connect()
        conn.isolation_level = None
        max_retries = 20
        try:
            for attempt in range(max_retries):
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    if _artificial_delay > 0:
                        time.sleep(_artificial_delay)
                    cursor = conn.execute(
                        "UPDATE users SET balance = balance - ? WHERE username = ? AND balance >= ?",
                        (amount, username, amount),
                    )
                    if cursor.rowcount == 1:
                        conn.execute("COMMIT")
                        return True
                    exists = conn.execute(
                        "SELECT 1 FROM users WHERE username = ?",
                        (username,),
                    ).fetchone()
                    conn.execute("ROLLBACK")
                    if exists is None:
                        raise KeyError(username)
                    return False
                except sqlite3.OperationalError as exc:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    if "locked" in str(exc).lower() and attempt < max_retries - 1:
                        time.sleep(0.01 * (attempt + 1))
                        continue
                    raise
                except Exception:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    raise
            raise sqlite3.OperationalError("database is locked")
        finally:
            conn.close()