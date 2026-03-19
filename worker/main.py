"""
Worker node — FastAPI application.
Embeddings are pre-computed at Docker build time. No sentence-transformers at runtime.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.schemas import (
    WorkerHealthResponse,
    WorkerSearchRequest,
    WorkerSearchResponse,
    WorkerSearchResult,
)
from worker.index import ShardIndex


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "worker_id": WORKER_ID,
            "shard_id": str(SHARD_ID),
        })


def setup_logging() -> None:
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)


setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKER_ID:  str  = os.environ.get("WORKER_ID",  "search-worker-1")
SHARD_ID:   int  = int(os.environ.get("SHARD_ID",  "0"))
SHARD_COUNT: int = int(os.environ.get("SHARD_COUNT", "3"))
DATA_DIR:   Path = Path(os.environ.get("DATA_DIR", "/app/data"))
START_TIME: float = time.time()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title=f"Search Worker — {WORKER_ID}", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_shard_index: ShardIndex
_queries_served: int = 0


@app.on_event("startup")
async def startup() -> None:
    global _shard_index, _queries_served
    _queries_served = 0
    logger.info("Worker %s starting (shard %d)", WORKER_ID, SHARD_ID)
    shard_dir = DATA_DIR / f"shard_{SHARD_ID}"
    _shard_index = ShardIndex(shard_id=SHARD_ID, worker_id=WORKER_ID, shard_dir=shard_dir)
    _shard_index.load()
    logger.info("Worker %s ready — %d docs indexed", WORKER_ID, _shard_index.document_count)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[type-arg]
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - t0) * 1000
    logger.info(json.dumps({
        "event": "request", "trace_id": trace_id,
        "method": request.method, "path": request.url.path,
        "status_code": response.status_code, "latency_ms": round(latency_ms, 2),
    }))
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/search", response_model=WorkerSearchResponse)
async def search(req: WorkerSearchRequest) -> WorkerSearchResponse:
    global _queries_served
    t0 = time.perf_counter()

    query_vec  = np.array(req.query_embedding, dtype=np.float32)
    raw        = _shard_index.search(query_vec, req.top_k)
    latency_ms = (time.perf_counter() - t0) * 1000
    _queries_served += 1

    results = [
        WorkerSearchResult(
            doc_id=r["doc_id"], score=r["score"], text=r["text"],
            worker_id=WORKER_ID, shard_id=SHARD_ID,
        )
        for r in raw
    ]

    logger.info(json.dumps({
        "event": "search", "trace_id": req.trace_id,
        "shard_id": SHARD_ID, "worker_id": WORKER_ID,
        "latency_ms": round(latency_ms, 2), "num_results": len(results),
    }))

    return WorkerSearchResponse(
        results=results, worker_id=WORKER_ID, shard_id=SHARD_ID,
        latency_ms=round(latency_ms, 2), trace_id=req.trace_id,
    )


@app.get("/health", response_model=WorkerHealthResponse)
async def health() -> WorkerHealthResponse:
    return WorkerHealthResponse(
        worker_id=WORKER_ID, shard_id=SHARD_ID, status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 2),
        document_count=_shard_index.document_count,
        index_size_bytes=_shard_index.index_size_bytes,
    )


@app.get("/corpus/sample")
async def corpus_sample(n: int = Query(default=20, ge=1, le=100)) -> dict:
    """Return a random sample of documents for the corpus browser."""
    return {
        "shard_id":   SHARD_ID,
        "worker_id":  WORKER_ID,
        "domain":     _shard_index.domain,
        "documents":  _shard_index.sample(n),
        "total_docs": _shard_index.document_count,
    }


@app.get("/ready")
async def ready() -> dict:
    if _shard_index.document_count == 0:
        raise HTTPException(status_code=503, detail="Index not ready")
    return {"status": "ready", "doc_count": _shard_index.document_count}
