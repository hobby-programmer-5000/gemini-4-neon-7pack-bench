"""Daily settlement reporting."""
from __future__ import annotations

from collections import defaultdict
from datetime import timezone
from storage import LedgerStore


def daily_volume_by_source_currency(store: LedgerStore) -> dict[str, dict[str, float]]:
    """Aggregate daily transferred source amounts by UTC date (YYYY-MM-DD) and currency.

    BUG 4: Uses entry.created_at.strftime('%Y-%m-%d') WITHOUT converting timezone-aware
    timestamps to UTC first, causing off-by-one day bucketing for non-UTC offsets (e.g. KST +09:00)!
    Also accumulates floats instead of exact Decimal.
    """
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for entry in store.entries:
        day_key = entry.created_at.strftime("%Y-%m-%d")
        buckets[day_key][entry.source_currency] += entry.amount_source
    return {day: dict(cur_map) for day, cur_map in buckets.items()}
