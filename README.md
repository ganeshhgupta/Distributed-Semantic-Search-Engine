# SearchOS — Distributed Semantic Search Engine

A production-grade distributed semantic search engine built as a portfolio
project demonstrating distributed systems engineering: consistent hashing,
parallel fan-out, fault tolerance, and real-time observability.

---

## Architecture

```
                          ┌───────────────────────────────┐
                          │           Client               │
                          │   (Browser / curl / locust)    │
                          └──────────────┬────────────────┘
                                         │ POST /search
                                         ▼
                          ┌───────────────────────────────┐
                          │         Coordinator            │
                          │                               │
                          │  ┌─────────────────────────┐  │
                          │  │  Consistent Hash Ring    │  │
                          │  │  (MD5, 150 vnodes/node)  │  │
                          │  └─────────────────────────┘  │
                          │                               │
                          │  1. Embed query (MiniLM-L6)   │
                          │  2. Fan-out → healthy workers  │
                          │  3. Merge & re-rank top-K      │
                          │  4. Return trace-annotated resp│
                          └───┬───────────┬───────────┬───┘
                              │           │           │
                    asyncio   │   asyncio  │   asyncio │
                    gather()  │           │           │
                              ▼           ▼           ▼
              ┌───────────────┐  ┌────────────┐  ┌───────────────┐
              │   Worker-1    │  │  Worker-2  │  │   Worker-3    │
              │  (Shard 0)    │  │  (Shard 1) │  │   (Shard 2)   │
              │               │  │            │  │               │
              │ FAISS         │  │ FAISS      │  │ FAISS         │
              │ IndexFlatIP   │  │ IndexFlatIP│  │ IndexFlatIP   │
              │ ~4 000 docs   │  │ ~4 000 docs│  │ ~4 000 docs   │
              └───────────────┘  └────────────┘  └───────────────┘
```

### Key design decisions

| Concern | Choice | Why |
|---|---|---|
| Shard assignment | Consistent hash ring (MD5, 150 vnodes) | O(log N) lookup, minimal key migration on node change |
| Vector index | FAISS `IndexFlatIP` | Exact cosine similarity on normalized embeddings, no approximation overhead |
| Fan-out | `asyncio.gather` over all healthy workers | Latency bounded by slowest worker, not sum |
| Fault tolerance | Background health poller (10 s interval) | Coordinator skips down workers, logs degraded mode |
| Persistence | numpy + JSON per shard on disk | Workers survive restarts without re-downloading data |
| Observability | Structured JSON logs + trace IDs | Every log line correlatable across coordinator and workers |

---

## Project structure

```
distributed-semantic-search/
├── coordinator/
│   ├── main.py          # FastAPI coordinator app, fan-out, merge, metrics
│   ├── hash_ring.py     # Consistent hash ring (MD5, virtual nodes)
│   ├── merger.py        # Top-K merge from multiple worker responses
│   ├── health_poller.py # Background worker health polling
│   └── metrics_store.py # In-memory rolling metrics (p50/p95/p99, QPS)
├── worker/
│   ├── main.py          # FastAPI worker app, FAISS search endpoint
│   ├── index.py         # ShardIndex: build/load/search FAISS index
│   └── embedder.py      # SentenceTransformer wrapper (MiniLM-L6-v2)
├── shared/
│   └── schemas.py       # Pydantic request/response models (shared)
├── frontend/
│   ├── src/
│   │   ├── pages/       # Landing, Search, System
│   │   ├── components/  # SearchBar, ResultCard, WorkerCard, LatencyChart, SkeletonCard
│   │   ├── hooks/       # useSearch, useMetrics, useClusterHealth
│   │   └── App.tsx
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── package.json
├── tests/
│   ├── test_hash_ring.py    # Determinism, distribution, removal stability
│   ├── test_merger.py       # Top-K correctness, deduplication, strategy agreement
│   └── test_health_poller.py # Healthy/unhealthy transitions, callback firing
├── benchmark/
│   ├── benchmark.py     # Async benchmark: p50/p95/p99 + histogram
│   └── locustfile.py    # Locust load test (SearchUser, HealthUser, BurstUser)
├── docker-compose.yml
├── Dockerfile.coordinator
├── Dockerfile.worker
├── Dockerfile.frontend
├── nginx.conf
└── requirements.txt
```

---

## Quick start

### Prerequisites

- Docker ≥ 24 and Docker Compose v2
- 8 GB RAM recommended (FAISS indexes + model weights)

### 1 — Build and start

```bash
cd distributed-semantic-search
docker compose up --build
```

On first run each worker downloads ~4 000 Wikipedia article chunks from
HuggingFace, embeds them with `all-MiniLM-L6-v2`, and saves the FAISS index
to its named volume.  Subsequent starts load from disk in seconds.

Expected startup time: 5–15 minutes (first run, embedding ~12 000 docs).

Services:

| URL | Description |
|---|---|
| http://localhost:3000 | React frontend |
| http://localhost:8000 | Coordinator REST API |
| http://localhost:8001 | Worker 1 (shard 0) |
| http://localhost:8002 | Worker 2 (shard 1) |
| http://localhost:8003 | Worker 3 (shard 2) |

### 2 — Run a query

```bash
curl -s -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "black holes event horizon", "top_k": 5}' | python -m json.tool
```

Sample output:

```json
{
  "results": [
    {
      "doc_id": "wiki-0000042-chunk-003",
      "score": 0.847291,
      "text": "Black hole: A black hole is a region of spacetime ...",
      "worker_id": "worker-2",
      "shard_id": 1,
      "rank": 1
    },
    ...
  ],
  "query": "black holes event horizon",
  "top_k": 5,
  "trace_id": "a3f1c2d4-...",
  "total_latency_ms": 34.7,
  "coordinator_overhead_ms": 12.1,
  "fanout_ms": 19.8,
  "merge_ms": 0.3,
  "workers_queried": ["worker-1", "worker-2", "worker-3"],
  "degraded": false
}
```

### 3 — Check cluster health

```bash
curl -s http://localhost:8000/health | python -m json.tool
curl -s http://localhost:8000/nodes  | python -m json.tool
curl -s http://localhost:8000/metrics | python -m json.tool
```

---

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Running the benchmark

```bash
# 1000 queries, 10 concurrent, against the running stack
python benchmark/benchmark.py --url http://localhost:8000 --queries 1000 --concurrency 10
```

Sample output:

```
============================================================
  Distributed Semantic Search Engine — Benchmark
============================================================
  Target:      http://localhost:8000
  Queries:     1000
  Top-K:       10
  Concurrency: 10
============================================================

  WALL-CLOCK LATENCY (client-side)
    p50:    42.31 ms
    p95:    78.14 ms
    p99:    94.67 ms
    min:    18.22 ms
    max:   142.09 ms

  SERVER TOTAL LATENCY
    p50:    38.90 ms
    p95:    71.22 ms
    p99:    88.44 ms

  LATENCY BREAKDOWN (p50)
    Embed overhead:   12.30 ms
    Fan-out time:     23.40 ms
    Merge time:        0.21 ms

  PER-WORKER QUERY DISTRIBUTION
    worker-1     ████████████████████ 1000 (100.0%)
    worker-2     ████████████████████ 1000 (100.0%)
    worker-3     ████████████████████ 1000 (100.0%)

  p99 SLA (<100ms): ✓ PASS — 94.67ms
```

---

## Running the Locust load test

```bash
# Interactive web UI
locust -f benchmark/locustfile.py --host http://localhost:8000

# Headless: 100 users, ramp up 10/s, run for 60 seconds
locust -f benchmark/locustfile.py --host http://localhost:8000 \
       --headless -u 100 -r 10 --run-time 60s
```

---

## Simulating degraded mode

```bash
# Stop one worker to trigger degraded mode
docker compose stop worker-2

# The coordinator will detect the outage within 10 s and fan out to worker-1 + worker-3 only
curl -s http://localhost:8000/health | python -m json.tool
# "degraded": true, "healthy_worker_count": 2, ...

# Restart to recover
docker compose start worker-2
```

---

## Frontend

Open http://localhost:3000 in your browser.

- **Landing page** (`/`) — search bar with animated gradient
- **Search results** (`/search?q=…`) — ranked result cards with worker badges,
  score bars, and query-term highlighting
- **System dashboard** (`/system`) — live cluster health, p50/p95/p99 latency
  chart (updates every 1 s), QPS, per-worker query distribution, dark mode

![Screenshot placeholder](docs/screenshot.png)

---

## Environment variables

### Coordinator

| Variable | Default | Description |
|---|---|---|
| `COORDINATOR_PORT` | `8000` | Listen port |
| `WORKER_URLS` | `http://worker-1:8001,...` | Comma-separated worker URLs |
| `HEALTH_POLL_INTERVAL` | `10` | Seconds between health polls |
| `FANOUT_TIMEOUT` | `2` | Per-worker search timeout (seconds) |

### Worker

| Variable | Default | Description |
|---|---|---|
| `WORKER_ID` | `worker-1` | Unique worker name |
| `WORKER_PORT` | `8001` | Listen port |
| `SHARD_ID` | `0` | This worker's shard index (0-based) |
| `SHARD_COUNT` | `3` | Total number of shards |
| `DATA_DIR` | `/data` | Directory for persisted shard data |
| `DOCS_PER_SHARD` | `4000` | Max documents to load per shard |

---

## API reference

### `POST /search`

```json
{ "query": "string", "top_k": 10 }
```

Returns merged, globally ranked results with full latency breakdown.

### `GET /health`

Coordinator health + per-worker status.

### `GET /nodes`

All registered worker nodes, their shard ranges, and document counts.

### `GET /metrics`

Real-time stats: p50/p95/p99, QPS, per-worker query distribution,
error rates, last-60s time-series history.

---

## Tech stack

| Layer | Technology |
|---|---|
| Coordinator / Worker API | Python 3.11 + FastAPI + uvicorn |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` (384-dim) |
| Vector index | FAISS `IndexFlatIP` (exact cosine similarity) |
| Dataset | HuggingFace `wikipedia` (20220301.en), streamed |
| HTTP client | `httpx` (async) |
| Data validation | Pydantic v2 |
| Frontend | React 18 + TypeScript (strict) + Vite |
| Styling | Tailwind CSS v3 + Inter + JetBrains Mono |
| Animations | Framer Motion |
| Charts | Recharts |
| Containerization | Docker + Docker Compose |
| Load testing | Locust |
| Unit tests | pytest + pytest-asyncio |
