"""Daily settlement reporting."""
from __future__ import annotations

from collections import defaultdict
from datetime import timezone
from decimal import Decimal

from storage import LedgerStore


def daily_volume_by_source_currency(store: LedgerStore) -> dict[str, dict[str, Decimal]]:
    """Aggregate daily transferred source amounts by UTC date (YYYY-MM-DD) and currency."""
    buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: defaultdict(lambda: Decimal("0"))
    )
    for entry in store.entries:
        ts = entry.created_at
        ts_utc = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
        day_key = ts_utc.strftime("%Y-%m-%d")
        buckets[day_key][entry.source_currency] += Decimal(str(entry.amount_source))
    return {day: dict(cur_map) for day, cur_map in buckets.items()}
