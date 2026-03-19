"""
Background health poller for the coordinator.

Polls each worker's GET /health endpoint every `poll_interval` seconds.
Updates the shared worker status registry, which the coordinator uses to
decide which workers to fan out to.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

import httpx

from shared.schemas import WorkerHealthResponse

logger = logging.getLogger(__name__)


class WorkerStatus:
    """Mutable status record for a single worker node."""

    def __init__(self, worker_id: str, url: str, shard_id: int) -> None:
        self.worker_id = worker_id
        self.url = url
        self.shard_id = shard_id
        self.healthy: bool = False
        self.last_health: Optional[WorkerHealthResponse] = None
        self.last_checked: float = 0.0
        self.consecutive_failures: int = 0
        self.queries_served: int = 0

    def mark_healthy(self, health: WorkerHealthResponse) -> None:
        self.healthy = True
        self.last_health = health
        self.last_checked = time.time()
        self.consecutive_failures = 0

    def mark_unhealthy(self) -> None:
        self.healthy = False
        self.last_checked = time.time()
        self.consecutive_failures += 1


class HealthPoller:
    """
    Polls all registered workers on a fixed interval in a background asyncio task.

    Usage:
        poller = HealthPoller(workers, poll_interval=10)
        asyncio.create_task(poller.run())
    """

    def __init__(
        self,
        workers: List[WorkerStatus],
        poll_interval: float = 10.0,
        timeout: float = 5.0,
        on_status_change: Optional[Callable[[WorkerStatus, bool], None]] = None,
    ) -> None:
        self._workers = workers
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._on_status_change = on_status_change
        self._running = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Main polling loop.  Run as a background asyncio task.
        Polls all workers concurrently, then sleeps until the next cycle.
        """
        self._running = True
        logger.info(
            "HealthPoller starting — polling %d worker(s) every %ss",
            len(self._workers), self._poll_interval,
        )
        while self._running:
            await self._poll_all()
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        self._running = False

    def healthy_workers(self) -> List[WorkerStatus]:
        return [w for w in self._workers if w.healthy]

    def all_workers(self) -> List[WorkerStatus]:
        return list(self._workers)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _poll_all(self) -> None:
        tasks = [self._poll_worker(w) for w in self._workers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_worker(self, worker: WorkerStatus) -> None:
        url = f"{worker.url}/health"
        was_healthy = worker.healthy
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                health_data = WorkerHealthResponse(**response.json())
                worker.mark_healthy(health_data)

                if not was_healthy:
                    logger.info(
                        "Worker %s (shard=%d) came ONLINE", worker.worker_id, worker.shard_id
                    )
                    if self._on_status_change:
                        self._on_status_change(worker, True)

        except Exception as exc:
            worker.mark_unhealthy()
            if was_healthy or worker.consecutive_failures == 1:
                logger.warning(
                    "Worker %s (shard=%d) is OFFLINE: %s",
                    worker.worker_id, worker.shard_id, exc,
                )
                if self._on_status_change:
                    self._on_status_change(worker, False)
            else:
                logger.debug(
                    "Worker %s still offline (failures=%d)",
                    worker.worker_id, worker.consecutive_failures,
                )
