// ---------------------------------------------------------------------------
// Domain types mirroring shared/schemas.py Pydantic models
// ---------------------------------------------------------------------------

export interface SearchResultItem {
  doc_id: string;
  score: number;
  text: string;
  worker_id: string;
  shard_id: number;
  rank: number;
}

export interface SearchResponse {
  results: SearchResultItem[];
  query: string;
  top_k: number;
  trace_id: string;
  total_latency_ms: number;
  coordinator_overhead_ms: number;
  fanout_ms: number;
  merge_ms: number;
  workers_queried: string[];
  degraded: boolean;
}

export interface WorkerHealthResponse {
  worker_id: string;
  shard_id: number;
  status: "healthy" | "degraded" | "down";
  uptime_seconds: number;
  document_count: number;
  index_size_bytes: number;
  trace_id?: string;
}

export interface HealthResponse {
  status: string;
  uptime_seconds: number;
  degraded: boolean;
  coordinator_id: string;
  workers: WorkerHealthResponse[];
  healthy_worker_count: number;
  total_worker_count: number;
}

export interface WorkerNodeInfo {
  worker_id: string;
  url: string;
  shard_id: number;
  shard_range: [number, number];
  document_count: number;
  status: "healthy" | "down";
  queries_served: number;
}

export interface MetricsSnapshot {
  timestamp: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  qps: number;
  total_queries: number;
  error_count: number;
  degraded_count: number;
  per_worker_queries: Record<string, number>;
  per_worker_errors: Record<string, number>;
}

export interface MetricsResponse {
  current: MetricsSnapshot;
  history: MetricsSnapshot[];
  total_queries: number;
  error_rate: number;
}
