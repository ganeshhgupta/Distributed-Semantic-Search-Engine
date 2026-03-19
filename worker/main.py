"""
Worker node — FastAPI application.

Environment variables:
    WORKER_ID       unique name, e.g. "worker-1"
    WORKER_PORT     port to listen on, default 8001
    SHARD_ID        integer shard this worker owns
    SHARD_COUNT     total number of shards / workers
    DATA_DIR        base directory for persisted shard data (default: /data)
    COORDINATOR_URL URL of the coordinator (for self-registration), e.g. http://coordinator:8000
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx
import numpy as np
from datasets import load_dataset
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

# Adjust Python path so shared/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.schemas import (
    WorkerHealthResponse,
    WorkerSearchRequest,
    WorkerSearchResponse,
    WorkerSearchResult,
)
from worker.embedder import Embedder
from worker.index import ShardIndex

# ---------------------------------------------------------------------------
# JSON structured logging
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "worker_id": os.environ.get("WORKER_ID", "unknown"),
            "shard_id": os.environ.get("SHARD_ID", "unknown"),
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

WORKER_ID: str = os.environ.get("WORKER_ID", "worker-1")
SHARD_ID: int = int(os.environ.get("SHARD_ID", "0"))
SHARD_COUNT: int = int(os.environ.get("SHARD_COUNT", "3"))
DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/data"))
COORDINATOR_URL: str = os.environ.get("COORDINATOR_URL", "http://coordinator:8000")
DOCS_PER_SHARD: int = int(os.environ.get("DOCS_PER_SHARD", "4000"))  # ~12k total / 3 shards

START_TIME: float = time.time()

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

app = FastAPI(title=f"Search Worker — {WORKER_ID}", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# These are populated during startup
_embedder: Embedder
_shard_index: ShardIndex
_queries_served: int = 0


# ---------------------------------------------------------------------------
# Dataset loading helpers
# ---------------------------------------------------------------------------

def _load_shard_documents() -> List[Dict[str, Any]]:
    """
    Load the Wikipedia dataset from HuggingFace and return the slice that
    belongs to this shard.

    We stream through the dataset and assign each article to shard
    (article_index % SHARD_COUNT).  Each article is chunked into ~250-token
    segments using a simple whitespace split.
    """
    logger.info("Loading Wikipedia dataset for shard %d/%d …", SHARD_ID, SHARD_COUNT)

    shard_dir = DATA_DIR / f"shard_{SHARD_ID}"
    shard_dir.mkdir(parents=True, exist_ok=True)

    # If raw metadata already exists, skip the download
    raw_meta_path = shard_dir / "raw_metadata.json"
    if raw_meta_path.exists():
        logger.info("Raw shard metadata already on disk, skipping download")
        with open(raw_meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    dataset = load_dataset(
        "wikipedia",
        "20220301.en",
        split="train",
        streaming=True,
        trust_remote_code=True,
    )

    documents: List[Dict[str, Any]] = []
    article_idx = 0
    chunk_size_words = 250  # approximate 200-300 token chunks

    for article in dataset:
        if article_idx % SHARD_COUNT == SHARD_ID:
            text: str = article["text"]  # type: ignore[index]
            title: str = article["title"]  # type: ignore[index]
            words = text.split()

            for chunk_i, start in enumerate(range(0, len(words), chunk_size_words)):
                chunk_words = words[start : start + chunk_size_words]
                if len(chunk_words) < 20:
                    continue  # skip tiny tail chunks
                chunk_text = " ".join(chunk_words)
                doc_id = f"wiki-{article_idx:07d}-chunk-{chunk_i:03d}"
                documents.append(
                    {
                        "doc_id": doc_id,
                        "text": f"{title}: {chunk_text}",
                    }
                )

            if len(documents) >= DOCS_PER_SHARD:
                break

        article_idx += 1

    logger.info("Loaded %d document chunks for shard %d", len(documents), SHARD_ID)

    with open(raw_meta_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False)

    return documents


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup() -> None:
    global _embedder, _shard_index, _queries_served
    _queries_served = 0

    logger.info("Starting worker %s (shard %d)", WORKER_ID, SHARD_ID)

    _embedder = Embedder()

    shard_dir = DATA_DIR / f"shard_{SHARD_ID}"
    shard_dir.mkdir(parents=True, exist_ok=True)

    _shard_index = ShardIndex(
        shard_id=SHARD_ID,
        worker_id=WORKER_ID,
        shard_dir=shard_dir,
        embedder=_embedder,
    )

    # Try to load from disk; if not available, download dataset and build
    emb_path = shard_dir / "embeddings.npy"
    meta_path = shard_dir / "metadata.json"

    if emb_path.exists() and meta_path.exists():
        _shard_index.load_or_build()
    else:
        documents = _load_shard_documents()
        _shard_index.load_or_build(documents=documents)

    logger.info(
        "Worker %s ready — %d documents indexed",
        WORKER_ID, _shard_index.document_count,
    )


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[type-arg]
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
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
            "worker_id": WORKER_ID,
        })
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/search", response_model=WorkerSearchResponse)
async def search(req: WorkerSearchRequest) -> WorkerSearchResponse:
    global _queries_served
    t0 = time.perf_counter()

    query_vec = np.array(req.query_embedding, dtype=np.float32)
    raw_results = _shard_index.search(query_vec, req.top_k)

    latency_ms = (time.perf_counter() - t0) * 1000
    _queries_served += 1

    results = [
        WorkerSearchResult(
            doc_id=r["doc_id"],
            score=r["score"],
            text=r["text"],
            worker_id=WORKER_ID,
            shard_id=SHARD_ID,
        )
        for r in raw_results
    ]

    logger.info(
        json.dumps({
            "event": "search",
            "trace_id": req.trace_id,
            "shard_id": SHARD_ID,
            "worker_id": WORKER_ID,
            "latency_ms": round(latency_ms, 2),
            "num_results": len(results),
        })
    )

    return WorkerSearchResponse(
        results=results,
        worker_id=WORKER_ID,
        shard_id=SHARD_ID,
        latency_ms=round(latency_ms, 2),
        trace_id=req.trace_id,
    )


@app.get("/health", response_model=WorkerHealthResponse)
async def health(trace_id: str = "") -> WorkerHealthResponse:
    uptime = time.time() - START_TIME
    return WorkerHealthResponse(
        worker_id=WORKER_ID,
        shard_id=SHARD_ID,
        status="healthy",
        uptime_seconds=round(uptime, 2),
        document_count=_shard_index.document_count,
        index_size_bytes=_shard_index.index_size_bytes,
        trace_id=trace_id or None,
    )


@app.get("/ready")
async def ready() -> dict:
    """Kubernetes-style readiness probe."""
    if _shard_index.document_count == 0:
        raise HTTPException(status_code=503, detail="Index not ready")
    return {"status": "ready", "doc_count": _shard_index.document_count}


# ---------------------------------------------------------------------------
# Entry point for direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("WORKER_PORT", "8001"))
    uvicorn.run("worker.main:app", host="0.0.0.0", port=port, reload=False)
