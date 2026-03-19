"""
In-memory rolling metrics store for the coordinator.

Keeps the last N request latency breakdowns and computes percentile
statistics on demand.  Also tracks per-worker query counts and error rates.
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from shared.schemas import LatencyBreakdown, MetricsSnapshot


class MetricsStore:
    """
    Thread-safe (asyncio-single-threaded) rolling metrics store.

    Stores up to `max_requests` individual LatencyBreakdown records and
    up to `max_snapshots` per-second aggregate snapshots for charting.
    """

    def __init__(self, max_requests: int = 1000, max_snapshots: int = 60) -> None:
        self._max_requests = max_requests
        self._max_snapshots = max_snapshots

        # Ring buffer of individual request latency records
        self._requests: Deque[LatencyBreakdown] = deque(maxlen=max_requests)

        # Per-second aggregate snapshots (for time-series charts)
        self._snapshots: Deque[MetricsSnapshot] = deque(maxlen=max_snapshots)

        # Counters (monotonically increasing)
        self._total_queries: int = 0
        self._error_count: int = 0
        self._degraded_count: int = 0

        # Per-worker counters
        self._worker_queries: Dict[str, int] = {}
        self._worker_errors: Dict[str, int] = {}

        # For QPS computation
        self._last_snapshot_time: float = time.time()
        self._queries_since_last_snapshot: int = 0

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def record(self, breakdown: LatencyBreakdown, error: bool = False) -> None:
        """Record a completed request."""
        self._requests.append(breakdown)
        self._total_queries += 1
        self._queries_since_last_snapshot += 1

        if error:
            self._error_count += 1

        if breakdown.degraded:
            self._degraded_count += 1

        for worker_id, _lat in breakdown.worker_latencies.items():
            self._worker_queries[worker_id] = self._worker_queries.get(worker_id, 0) + 1
            if error:
                self._worker_errors[worker_id] = self._worker_errors.get(worker_id, 0) + 1

    def record_error(self, worker_id: str) -> None:
        """Record a worker-level error without a full breakdown."""
        self._error_count += 1
        self._worker_errors[worker_id] = self._worker_errors.get(worker_id, 0) + 1

    def take_snapshot(self) -> Optional[MetricsSnapshot]:
        """
        Compute and store a per-second aggregate snapshot.

        Should be called approximately once per second by a background task.
        Returns None if no requests have been recorded yet.
        """
        now = time.time()
        elapsed = now - self._last_snapshot_time
        if elapsed <= 0:
            elapsed = 1.0

        qps = self._queries_since_last_snapshot / elapsed

        # Reset window counters
        self._last_snapshot_time = now
        self._queries_since_last_snapshot = 0

        if not self._requests:
            snapshot = MetricsSnapshot(
                timestamp=now,
                p50_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                qps=round(qps, 2),
                total_queries=self._total_queries,
                error_count=self._error_count,
                degraded_count=self._degraded_count,
                per_worker_queries=dict(self._worker_queries),
                per_worker_errors=dict(self._worker_errors),
            )
        else:
            latencies = sorted(r.total_ms for r in self._requests)
            snapshot = MetricsSnapshot(
                timestamp=now,
                p50_ms=round(_percentile(latencies, 50), 2),
                p95_ms=round(_percentile(latencies, 95), 2),
                p99_ms=round(_percentile(latencies, 99), 2),
                qps=round(qps, 2),
                total_queries=self._total_queries,
                error_count=self._error_count,
                degraded_count=self._degraded_count,
                per_worker_queries=dict(self._worker_queries),
                per_worker_errors=dict(self._worker_errors),
            )

        self._snapshots.append(snapshot)
        return snapshot

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def current_snapshot(self) -> MetricsSnapshot:
        """Return the most recent snapshot (or zeros if none yet)."""
        if self._snapshots:
            return self._snapshots[-1]
        return MetricsSnapshot(
            timestamp=time.time(),
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            qps=0.0,
            total_queries=self._total_queries,
            error_count=self._error_count,
            degraded_count=self._degraded_count,
            per_worker_queries=dict(self._worker_queries),
            per_worker_errors=dict(self._worker_errors),
        )

    def history(self) -> List[MetricsSnapshot]:
        """Return all stored snapshots (oldest first)."""
        return list(self._snapshots)

    @property
    def total_queries(self) -> int:
        return self._total_queries

    @property
    def error_rate(self) -> float:
        if self._total_queries == 0:
            return 0.0
        return self._error_count / self._total_queries

    def recent_latencies(self) -> List[LatencyBreakdown]:
        """Return recent individual request records."""
        return list(self._requests)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_values: List[float], pct: int) -> float:
    """Compute the given percentile from a sorted list using linear interpolation."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    # Nearest rank method
    k = (pct / 100) * (n - 1)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_values[lo]
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac
