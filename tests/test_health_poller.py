"""
Unit tests for the health poller.

Tests:
  - Healthy worker is correctly marked as healthy
  - Failing worker is marked as unhealthy
  - Status-change callback is invoked on transitions
  - healthy_workers() only returns currently healthy nodes
  - consecutive_failures counter increments correctly
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coordinator.health_poller import HealthPoller, WorkerStatus
from shared.schemas import WorkerHealthResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_worker(worker_id: str = "worker-1", url: str = "http://w1:8001", shard_id: int = 0) -> WorkerStatus:
    return WorkerStatus(worker_id=worker_id, url=url, shard_id=shard_id)


def make_health_response(worker_id: str = "worker-1", shard_id: int = 0) -> WorkerHealthResponse:
    return WorkerHealthResponse(
        worker_id=worker_id,
        shard_id=shard_id,
        status="healthy",
        uptime_seconds=42.0,
        document_count=4000,
        index_size_bytes=6_144_000,
    )


# ---------------------------------------------------------------------------
# WorkerStatus unit tests
# ---------------------------------------------------------------------------

class TestWorkerStatus:
    def test_initial_state(self) -> None:
        w = make_worker()
        assert w.healthy is False
        assert w.last_health is None
        assert w.consecutive_failures == 0

    def test_mark_healthy(self) -> None:
        w = make_worker()
        h = make_health_response()
        w.mark_healthy(h)
        assert w.healthy is True
        assert w.last_health == h
        assert w.consecutive_failures == 0
        assert w.last_checked > 0

    def test_mark_unhealthy(self) -> None:
        w = make_worker()
        w.mark_healthy(make_health_response())  # start healthy
        w.mark_unhealthy()
        assert w.healthy is False
        assert w.consecutive_failures == 1

    def test_consecutive_failures_increment(self) -> None:
        w = make_worker()
        for i in range(5):
            w.mark_unhealthy()
        assert w.consecutive_failures == 5

    def test_recovery_resets_failure_count(self) -> None:
        w = make_worker()
        w.mark_unhealthy()
        w.mark_unhealthy()
        w.mark_healthy(make_health_response())
        assert w.consecutive_failures == 0
        assert w.healthy is True


# ---------------------------------------------------------------------------
# HealthPoller integration tests (async, with mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestHealthPollerAsync:
    async def _run_one_poll(self, poller: HealthPoller) -> None:
        """Execute exactly one poll cycle."""
        await poller._poll_all()

    async def test_healthy_worker_marked_healthy(self) -> None:
        worker = make_worker()
        poller = HealthPoller([worker], poll_interval=999)

        health_json = make_health_response().model_dump()

        mock_response = MagicMock()
        mock_response.json.return_value = health_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await self._run_one_poll(poller)

        assert worker.healthy is True
        assert worker.last_health is not None
        assert worker.last_health.document_count == 4000

    async def test_unreachable_worker_marked_unhealthy(self) -> None:
        worker = make_worker()
        poller = HealthPoller([worker], poll_interval=999)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await self._run_one_poll(poller)

        assert worker.healthy is False
        assert worker.consecutive_failures == 1

    async def test_status_change_callback_on_recovery(self) -> None:
        """Callback should fire when a worker comes back online."""
        worker = make_worker()
        worker.healthy = False  # start offline

        status_changes: List[tuple[str, bool]] = []

        def on_change(w: WorkerStatus, is_healthy: bool) -> None:
            status_changes.append((w.worker_id, is_healthy))

        poller = HealthPoller([worker], poll_interval=999, on_status_change=on_change)

        health_json = make_health_response().model_dump()
        mock_response = MagicMock()
        mock_response.json.return_value = health_json
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await self._run_one_poll(poller)

        assert len(status_changes) == 1
        assert status_changes[0] == ("worker-1", True)

    async def test_status_change_callback_on_failure(self) -> None:
        """Callback should fire when a healthy worker goes offline."""
        worker = make_worker()
        worker.mark_healthy(make_health_response())  # start online

        status_changes: List[tuple[str, bool]] = []

        def on_change(w: WorkerStatus, is_healthy: bool) -> None:
            status_changes.append((w.worker_id, is_healthy))

        poller = HealthPoller([worker], poll_interval=999, on_status_change=on_change)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await self._run_one_poll(poller)

        assert len(status_changes) == 1
        assert status_changes[0] == ("worker-1", False)

    async def test_healthy_workers_excludes_down_nodes(self) -> None:
        w1 = make_worker("worker-1", "http://w1:8001", 0)
        w2 = make_worker("worker-2", "http://w2:8002", 1)
        w1.mark_healthy(make_health_response("worker-1", 0))
        # w2 remains unhealthy

        poller = HealthPoller([w1, w2], poll_interval=999)
        healthy = poller.healthy_workers()
        assert len(healthy) == 1
        assert healthy[0].worker_id == "worker-1"

    async def test_all_workers_returns_all(self) -> None:
        w1 = make_worker("worker-1", "http://w1:8001", 0)
        w2 = make_worker("worker-2", "http://w2:8002", 1)
        poller = HealthPoller([w1, w2], poll_interval=999)
        assert len(poller.all_workers()) == 2

    async def test_multiple_workers_polled_concurrently(self) -> None:
        """All workers should be polled in a single cycle."""
        workers = [make_worker(f"w{i}", f"http://w{i}:800{i}", i) for i in range(3)]
        call_counts: dict[str, int] = {}

        poller = HealthPoller(workers, poll_interval=999)
        health_json = make_health_response().model_dump()

        async def mock_get(url: str, **kwargs) -> MagicMock:  # type: ignore[type-arg]
            worker_id = url.split("//")[1].split(":")[0]
            call_counts[worker_id] = call_counts.get(worker_id, 0) + 1
            mock_resp = MagicMock()
            mock_resp.json.return_value = health_json
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await self._run_one_poll(poller)

        assert len(call_counts) == 3  # all 3 workers were polled


# ---------------------------------------------------------------------------
# Degraded mode
# ---------------------------------------------------------------------------

class TestDegradedMode:
    def test_healthy_workers_subset(self) -> None:
        w1 = make_worker("worker-1", "http://w1", 0)
        w2 = make_worker("worker-2", "http://w2", 1)
        w3 = make_worker("worker-3", "http://w3", 2)

        w1.mark_healthy(make_health_response("worker-1", 0))
        w2.mark_healthy(make_health_response("worker-2", 1))
        # w3 is down

        poller = HealthPoller([w1, w2, w3], poll_interval=999)
        healthy = poller.healthy_workers()
        all_w = poller.all_workers()

        assert len(healthy) == 2
        assert len(all_w) == 3
        # Degraded = not all workers are healthy
        assert len(healthy) < len(all_w)
