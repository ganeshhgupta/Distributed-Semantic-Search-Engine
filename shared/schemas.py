"""
Shared Pydantic schemas used by coordinator and worker nodes.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Worker-facing schemas
# ---------------------------------------------------------------------------

class WorkerSearchRequest(BaseModel):
    query_embedding: List[float] = Field(..., description="Pre-computed query embedding vector")
    top_k: int = Field(default=10, ge=1, le=100)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class WorkerSearchResult(BaseModel):
    doc_id: str
    score: float
    text: str
    worker_id: str
    shard_id: int


class WorkerSearchResponse(BaseModel):
    results: List[WorkerSearchResult]
    worker_id: str
    shard_id: int
    latency_ms: float
    trace_id: str


class WorkerHealthResponse(BaseModel):
    worker_id: str
    shard_id: int
    status: str  # "healthy" | "degraded"
    uptime_seconds: float
    document_count: int
    index_size_bytes: int
    trace_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Coordinator-facing schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=100)


class SearchResultItem(BaseModel):
    doc_id: str
    score: float
    text: str
    worker_id: str
    shard_id: int
    rank: int


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    query: str
    top_k: int
    trace_id: str
    total_latency_ms: float
    coordinator_overhead_ms: float
    fanout_ms: float
    merge_ms: float
    workers_queried: List[str]
    degraded: bool = False


class WorkerNodeInfo(BaseModel):
    worker_id: str
    url: str
    shard_id: int
    shard_range: tuple[int, int]
    document_count: int
    status: str  # "healthy" | "down"
    queries_served: int = 0


class NodesResponse(BaseModel):
    nodes: List[WorkerNodeInfo]
    total_documents: int
    degraded: bool


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    degraded: bool
    coordinator_id: str
    workers: List[WorkerHealthResponse]
    healthy_worker_count: int
    total_worker_count: int


# ---------------------------------------------------------------------------
# Metrics schemas
# ---------------------------------------------------------------------------

class LatencyBreakdown(BaseModel):
    trace_id: str
    query: str
    total_ms: float
    coordinator_overhead_ms: float
    fanout_ms: float
    merge_ms: float
    worker_latencies: dict[str, float]
    timestamp: float
    degraded: bool = False


class MetricsSnapshot(BaseModel):
    timestamp: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    qps: float
    total_queries: int
    error_count: int
    degraded_count: int
    per_worker_queries: dict[str, int]
    per_worker_errors: dict[str, int]


class MetricsResponse(BaseModel):
    current: MetricsSnapshot
    history: List[MetricsSnapshot]
    total_queries: int
    error_rate: float
