"""
Coordinator node — FastAPI application.

Environment variables:
    COORDINATOR_PORT    port to listen on (default 8000)
    WORKER_URLS         comma-separated list of worker base URLs
                        e.g. "http://worker-1:8001,http://worker-2:8002,http://worker-3:8003"
    HEALTH_POLL_INTERVAL  seconds between health polls (default 10)
    FANOUT_TIMEOUT      seconds to wait for each worker search (default 2)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from coordinator.health_poller import WorkerStatus

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# Adjust Python path so shared/ and coordinator/ are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from coordinator.hash_ring import ConsistentHashRing
from coordinator.health_poller import HealthPoller, WorkerStatus
from coordinator.merger import merge_results
from coordinator.metrics_store import MetricsStore
from shared.schemas import (
    HealthResponse,
    LatencyBreakdown,
    MetricsResponse,
    NodesResponse,
    SearchRequest,
    SearchResponse,
    WorkerHealthResponse,
    WorkerNodeInfo,
    WorkerSearchRequest,
    WorkerSearchResponse,
)
from worker.embedder import Embedder


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "coordinator",
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COORDINATOR_PORT: int = int(os.environ.get("PORT", os.environ.get("COORDINATOR_PORT", "8000")))
WORKER_URLS_RAW: str = os.environ.get(
    "WORKER_URLS",
    "http://worker-1:8001,http://worker-2:8002,http://worker-3:8003",
)
WORKER_URLS: List[str] = [u.strip() for u in WORKER_URLS_RAW.split(",") if u.strip()]
HEALTH_POLL_INTERVAL: float = float(os.environ.get("HEALTH_POLL_INTERVAL", "10"))
FANOUT_TIMEOUT: float = float(os.environ.get("FANOUT_TIMEOUT", "2"))
COORDINATOR_ID: str = f"coordinator-{uuid.uuid4().hex[:8]}"

START_TIME: float = time.time()

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

app = FastAPI(title="Search Coordinator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Populated at startup
_embedder: Embedder
_worker_statuses: List[WorkerStatus] = []
_health_poller: HealthPoller
_metrics_store: MetricsStore
_hash_ring: ConsistentHashRing
_snapshot_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------

def _build_worker_statuses() -> List[WorkerStatus]:
    statuses = []
    for shard_id, url in enumerate(WORKER_URLS):
        worker_id = f"worker-{shard_id + 1}"
        statuses.append(WorkerStatus(worker_id=worker_id, url=url, shard_id=shard_id))
    return statuses


def _build_hash_ring(workers: List[WorkerStatus]) -> ConsistentHashRing:
    ring = ConsistentHashRing(vnodes=150)
    for w in workers:
        ring.add_node(w.worker_id)
    return ring


async def _snapshot_loop(store: MetricsStore, interval: float = 1.0) -> None:
    """Background task: take a metrics snapshot every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        store.take_snapshot()


@app.on_event("startup")
async def startup() -> None:
    global _embedder, _worker_statuses, _health_poller, _metrics_store, _hash_ring, _snapshot_task

    logger.info("Coordinator %s starting up", COORDINATOR_ID)

    _embedder = Embedder()
    _metrics_store = MetricsStore(max_requests=1000, max_snapshots=60)
    _worker_statuses = _build_worker_statuses()
    _hash_ring = _build_hash_ring(_worker_statuses)

    _health_poller = HealthPoller(
        workers=_worker_statuses,
        poll_interval=HEALTH_POLL_INTERVAL,
        timeout=5.0,
    )

    # Kick off initial health poll immediately so we know which workers are up
    asyncio.create_task(_health_poller.run())

    # Background snapshot task
    _snapshot_task = asyncio.create_task(_snapshot_loop(_metrics_store))

    logger.info(
        "Coordinator ready — managing %d worker(s): %s",
        len(WORKER_URLS), WORKER_URLS,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    _health_poller.stop()
    if _snapshot_task:
        _snapshot_task.cancel()


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[type-arg]
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    t0 = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        json.dumps({
            "event": "request",
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 2),
        })
    )
    response.headers["X-Trace-ID"] = trace_id
    return response


# ---------------------------------------------------------------------------
# Fan-out helpers
# ---------------------------------------------------------------------------

async def _search_worker(
    client: httpx.AsyncClient,
    worker: WorkerStatus,
    req: WorkerSearchRequest,
) -> Optional[WorkerSearchResponse]:
    """
    Send a search request to a single worker.

    Returns None if the worker is unreachable or returns an error.
    """
    url = f"{worker.url}/search"
    try:
        t0 = time.perf_counter()
        response = await client.post(
            url,
            json=req.model_dump(),
            timeout=FANOUT_TIMEOUT,
            headers={"X-Trace-ID": req.trace_id},
        )
        response.raise_for_status()
        elapsed = (time.perf_counter() - t0) * 1000
        data = response.json()
        logger.info(
            json.dumps({
                "event": "worker_search",
                "trace_id": req.trace_id,
                "worker_id": worker.worker_id,
                "shard_id": worker.shard_id,
                "latency_ms": round(elapsed, 2),
                "num_results": len(data.get("results", [])),
            })
        )
        return WorkerSearchResponse(**data)
    except Exception as exc:
        logger.warning(
            json.dumps({
                "event": "worker_search_error",
                "trace_id": req.trace_id,
                "worker_id": worker.worker_id,
                "error": str(exc),
            })
        )
        _metrics_store.record_error(worker.worker_id)
        return None


async def _fanout(
    query_embedding: List[float],
    top_k: int,
    trace_id: str,
) -> tuple[List[WorkerSearchResponse], List[str], bool, float]:
    """
    Fan out a search request to all healthy workers in parallel.

    Returns:
        (responses, workers_queried, degraded, fanout_ms)
    """
    healthy = [w for w in _health_poller.healthy_workers() if w.worker_id not in _simulated_down]
    degraded = len(healthy) < len(_worker_statuses)

    if not healthy:
        raise HTTPException(status_code=503, detail="No healthy workers available")

    worker_req = WorkerSearchRequest(
        query_embedding=query_embedding,
        top_k=top_k,
        trace_id=trace_id,
    )

    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        tasks = [_search_worker(client, w, worker_req) for w in healthy]
        raw_responses = await asyncio.gather(*tasks)
    fanout_ms = (time.perf_counter() - t0) * 1000

    responses = [r for r in raw_responses if r is not None]
    workers_queried = [w.worker_id for w in healthy]

    # Update per-worker query counters
    for w in healthy:
        w.queries_served += 1

    return responses, workers_queried, degraded, fanout_ms


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request) -> SearchResponse:
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    t0 = time.perf_counter()

    # 1. Embed query
    embed_start = time.perf_counter()
    query_embedding = _embedder.embed_query(req.query)[0].tolist()
    coordinator_overhead_ms = (time.perf_counter() - embed_start) * 1000

    # 2. Fan out to workers
    responses, workers_queried, degraded, fanout_ms = await _fanout(
        query_embedding, req.top_k, trace_id
    )

    # 3. Merge results
    merge_start = time.perf_counter()
    merged = merge_results(responses, req.top_k)
    merge_ms = (time.perf_counter() - merge_start) * 1000

    total_ms = (time.perf_counter() - t0) * 1000

    # 4. Record metrics
    worker_latencies = {
        r.worker_id: r.latency_ms for r in responses
    }
    breakdown = LatencyBreakdown(
        trace_id=trace_id,
        query=req.query,
        total_ms=round(total_ms, 2),
        coordinator_overhead_ms=round(coordinator_overhead_ms, 2),
        fanout_ms=round(fanout_ms, 2),
        merge_ms=round(merge_ms, 2),
        worker_latencies=worker_latencies,
        timestamp=time.time(),
        degraded=degraded,
    )
    _metrics_store.record(breakdown)

    logger.info(
        json.dumps({
            "event": "search_complete",
            "trace_id": trace_id,
            "query": req.query[:80],
            "total_ms": round(total_ms, 2),
            "fanout_ms": round(fanout_ms, 2),
            "merge_ms": round(merge_ms, 2),
            "num_results": len(merged),
            "degraded": degraded,
        })
    )

    return SearchResponse(
        results=merged,
        query=req.query,
        top_k=req.top_k,
        trace_id=trace_id,
        total_latency_ms=round(total_ms, 2),
        coordinator_overhead_ms=round(coordinator_overhead_ms, 2),
        fanout_ms=round(fanout_ms, 2),
        merge_ms=round(merge_ms, 2),
        workers_queried=workers_queried,
        degraded=degraded,
    )


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    uptime = time.time() - START_TIME
    all_workers = _health_poller.all_workers()
    healthy_workers = _health_poller.healthy_workers()
    degraded = len(healthy_workers) < len(all_workers)

    worker_health_list: List[WorkerHealthResponse] = []
    for w in all_workers:
        if w.last_health:
            worker_health_list.append(w.last_health)
        else:
            worker_health_list.append(
                WorkerHealthResponse(
                    worker_id=w.worker_id,
                    shard_id=w.shard_id,
                    status="down",
                    uptime_seconds=0.0,
                    document_count=0,
                    index_size_bytes=0,
                )
            )

    return HealthResponse(
        status="degraded" if degraded else "healthy",
        uptime_seconds=round(uptime, 2),
        degraded=degraded,
        coordinator_id=COORDINATOR_ID,
        workers=worker_health_list,
        healthy_worker_count=len(healthy_workers),
        total_worker_count=len(all_workers),
    )


@app.get("/nodes", response_model=NodesResponse)
async def nodes() -> NodesResponse:
    all_workers = _health_poller.all_workers()
    shard_ranges = _hash_ring.get_shard_ranges()
    degraded = any(not w.healthy for w in all_workers)

    node_infos: List[WorkerNodeInfo] = []
    total_docs = 0

    for w in all_workers:
        doc_count = w.last_health.document_count if w.last_health else 0
        total_docs += doc_count
        shard_range = shard_ranges.get(w.worker_id, (0, 0))
        node_infos.append(
            WorkerNodeInfo(
                worker_id=w.worker_id,
                url=w.url,
                shard_id=w.shard_id,
                shard_range=shard_range,
                document_count=doc_count,
                status="healthy" if w.healthy else "down",
                queries_served=w.queries_served,
            )
        )

    return NodesResponse(
        nodes=node_infos,
        total_documents=total_docs,
        degraded=degraded,
    )


@app.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    return MetricsResponse(
        current=_metrics_store.current_snapshot(),
        history=_metrics_store.history(),
        total_queries=_metrics_store.total_queries,
        error_rate=round(_metrics_store.error_rate, 4),
    )


@app.get("/ready")
async def ready() -> dict:
    healthy = _health_poller.healthy_workers()
    if not healthy:
        raise HTTPException(status_code=503, detail="No healthy workers")
    return {"status": "ready", "healthy_workers": len(healthy)}


# ---------------------------------------------------------------------------
# Corpus browser — fan-out to all healthy workers
# ---------------------------------------------------------------------------

@app.get("/corpus/sample")
async def corpus_sample(n: int = 20) -> dict:
    """
    Return a random sample of documents from each healthy shard.
    Used by the frontend corpus browser.
    """
    healthy = _health_poller.healthy_workers()
    if not healthy:
        raise HTTPException(status_code=503, detail="No healthy workers")

    per_worker = max(1, n // len(healthy))

    async def fetch_sample(worker: "WorkerStatus") -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{worker.url}/corpus/sample?n={per_worker}")
                resp.raise_for_status()
                return resp.json()
        except Exception:
            return None

    results = await asyncio.gather(*[fetch_sample(w) for w in healthy])
    shards = [r for r in results if r is not None]

    all_docs = []
    for shard in shards:
        all_docs.extend(shard.get("documents", []))

    total_docs = sum(
        w.last_health.document_count for w in _health_poller.all_workers() if w.last_health
    )

    return {
        "shards": shards,
        "documents": all_docs,
        "total_docs": total_docs,
        "healthy_shards": len(shards),
    }


# ---------------------------------------------------------------------------
# Admin — demo fault-tolerance simulation (no auth needed for portfolio demo)
# ---------------------------------------------------------------------------

# Set of worker_ids currently in simulated-down state
_simulated_down: set[str] = set()
_sim_recovery_tasks: dict[str, "asyncio.Task[None]"] = {}


@app.post("/admin/simulate-down/{worker_id}")
async def simulate_down(worker_id: str) -> dict:
    """
    Mark a worker as down in the coordinator's view for `duration` seconds.
    The actual Render service keeps running — this only affects routing.
    """
    duration: int = 30

    target = next((w for w in _worker_statuses if w.worker_id == worker_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")

    _simulated_down.add(worker_id)
    target.healthy = False
    target.consecutive_failures = 99

    logger.info("DEMO: simulated worker %s as DOWN for %ds", worker_id, duration)

    # Cancel any existing recovery task
    if worker_id in _sim_recovery_tasks:
        _sim_recovery_tasks[worker_id].cancel()

    async def auto_recover() -> None:
        await asyncio.sleep(duration)
        _simulated_down.discard(worker_id)
        logger.info("DEMO: auto-recovering worker %s", worker_id)

    _sim_recovery_tasks[worker_id] = asyncio.create_task(auto_recover())

    return {
        "status": "simulated_down",
        "worker_id": worker_id,
        "auto_recover_seconds": duration,
        "message": f"Worker {worker_id} will auto-recover in {duration}s",
    }


@app.post("/admin/simulate-recover/{worker_id}")
async def simulate_recover(worker_id: str) -> dict:
    """Manually restore a simulated-down worker."""
    _simulated_down.discard(worker_id)
    if worker_id in _sim_recovery_tasks:
        _sim_recovery_tasks[worker_id].cancel()
        del _sim_recovery_tasks[worker_id]
    logger.info("DEMO: manually recovered worker %s", worker_id)
    return {"status": "recovered", "worker_id": worker_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("coordinator.main:app", host="0.0.0.0", port=COORDINATOR_PORT, reload=False)
