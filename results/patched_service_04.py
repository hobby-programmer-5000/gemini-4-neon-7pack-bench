"""Defensive root-cause patched service module."""
from __future__ import annotations

import ast
import contextlib
import hashlib
import hmac
import operator
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


class VulnerableService:
    def __init__(self, db_path: str, export_root: str, webhook_secret: bytes) -> None:
        self.db_path = db_path
        self.export_root = str(Path(export_root).resolve())
        self.webhook_secret = webhook_secret
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _init_db(self) -> None:
        with contextlib.closing(self._connect()) as conn:
            with conn:
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

    def add_user(self, username: str, role: str, balance: int) -> None:
        with contextlib.closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO users(username, role, balance) VALUES (?, ?, ?)",
                    (username, role, balance),
                )

    def search_users(self, username_query: str) -> list[dict[str, Any]]:
        with contextlib.closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, username, role, balance FROM users WHERE username = ?",
                (username_query,),
            ).fetchall()
            return [dict(r) for r in rows]

    def read_export_file(self, filename: str) -> str:
        root = Path(self.export_root).resolve()
        candidate = (root / filename).resolve()
        if candidate == root or not candidate.is_relative_to(root):
            raise PermissionError("Path outside export root")
        return candidate.read_text(encoding="utf-8")

    def verify_webhook_sig(self, payload: bytes, provided_sig: str) -> bool:
        expected = hmac.new(self.webhook_secret, payload, hashlib.sha256).hexdigest()
        if not isinstance(provided_sig, str) or len(provided_sig) != len(expected):
            return False
        try:
            expected_bytes = expected.encode("ascii")
            provided_bytes = provided_sig.encode("ascii")
        except UnicodeEncodeError:
            return False
        return hmac.compare_digest(expected_bytes, provided_bytes)

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
                    raise ValueError(f"Non-numeric variable value: {node.id}")
                return float(val)
            if isinstance(node, ast.UnaryOp):
                op_func = _UNARY_OPS.get(type(node.op))
                if op_func is None:
                    raise ValueError("Unsupported unary operator")
                return float(op_func(_eval_node(node.operand)))
            if isinstance(node, ast.BinOp):
                op_func = _BIN_OPS.get(type(node.op))
                if op_func is None:
                    raise ValueError("Unsupported binary operator")
                return float(op_func(_eval_node(node.left), _eval_node(node.right)))
            raise ValueError(f"Disallowed expression element: {type(node).__name__}")

        return float(_eval_node(tree))

    def withdraw(self, username: str, amount: int, _artificial_delay: float = 0.0) -> bool:
        if amount <= 0:
            raise ValueError("amount must be positive")

        max_attempts = 50
        for attempt in range(max_attempts):
            with contextlib.closing(self._connect()) as conn:
                conn.isolation_level = None
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    row = conn.execute(
                        "SELECT 1 FROM users WHERE username = ?",
                        (username,),
                    ).fetchone()
                    if row is None:
                        conn.execute("ROLLBACK")
                        raise KeyError(username)

                    if _artificial_delay > 0:
                        time.sleep(_artificial_delay)

                    cursor = conn.execute(
                        "UPDATE users SET balance = balance - ? WHERE username = ? AND balance >= ?",
                        (amount, username, amount),
                    )
                    conn.execute("COMMIT")
                    return cursor.rowcount == 1
                except sqlite3.OperationalError as exc:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    msg = str(exc).lower()
                    if ("locked" in msg or "busy" in msg) and attempt < max_attempts - 1:
                        time.sleep(0.01 * (attempt + 1))
                        continue
                    raise
                except Exception:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    raise
        return False