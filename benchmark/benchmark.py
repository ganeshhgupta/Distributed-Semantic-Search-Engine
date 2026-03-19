"""
Benchmark script — runs N queries against the coordinator and prints
p50/p95/p99 latency statistics along with a per-worker breakdown.

Usage:
    python benchmark/benchmark.py \
        --url http://localhost:8000 \
        --queries 1000 \
        --top-k 10 \
        --concurrency 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import time
from typing import List

import httpx

# ---------------------------------------------------------------------------
# Sample queries
# ---------------------------------------------------------------------------

SAMPLE_QUERIES = [
    "quantum computing applications in cryptography",
    "history of the Roman Empire",
    "machine learning for natural language processing",
    "climate change effects on biodiversity",
    "Renaissance art and architecture",
    "black holes and event horizons",
    "World War II Pacific theater battles",
    "protein folding and drug discovery",
    "ancient Egyptian mythology and religion",
    "deep learning convolutional neural networks",
    "economic impact of the Industrial Revolution",
    "CRISPR gene editing ethics",
    "philosophy of consciousness and free will",
    "international space station missions",
    "ocean acidification marine ecosystems",
    "Byzantine Empire culture and politics",
    "semiconductor physics transistor design",
    "Shakespeare's influence on English literature",
    "vaccination history and herd immunity",
    "cryptocurrency blockchain distributed ledger",
    "French Revolution causes and consequences",
    "superconductivity materials science",
    "Mongol Empire expansion trade routes",
    "neuroscience memory formation mechanisms",
    "solar energy photovoltaic technology",
    "Ottoman Empire decline and fall",
    "Antarctica ice sheet research glaciology",
    "artificial general intelligence safety",
    "medieval European feudal system",
    "DNA replication and transcription",
]


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def percentile(sorted_values: List[float], pct: int) -> float:
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = (pct / 100) * (n - 1)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_values[lo]
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def print_histogram(values: List[float], buckets: int = 10) -> None:
    if not values:
        return
    min_v, max_v = min(values), max(values)
    step = (max_v - min_v) / buckets if max_v > min_v else 1.0
    counts = [0] * buckets
    for v in values:
        idx = min(int((v - min_v) / step), buckets - 1)
        counts[idx] += 1
    bar_max = max(counts) or 1
    for i, count in enumerate(counts):
        lo = min_v + i * step
        hi = lo + step
        bar = "█" * int(40 * count / bar_max)
        print(f"  [{lo:6.1f}ms – {hi:6.1f}ms]  {bar} ({count})")


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

async def run_query(
    client: httpx.AsyncClient,
    base_url: str,
    query: str,
    top_k: int,
) -> dict:
    t0 = time.perf_counter()
    try:
        response = await client.post(
            f"{base_url}/search",
            json={"query": query, "top_k": top_k},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        wall_ms = (time.perf_counter() - t0) * 1000
        return {
            "success": True,
            "wall_ms": wall_ms,
            "total_latency_ms": data.get("total_latency_ms", wall_ms),
            "fanout_ms": data.get("fanout_ms", 0),
            "merge_ms": data.get("merge_ms", 0),
            "coordinator_overhead_ms": data.get("coordinator_overhead_ms", 0),
            "workers_queried": data.get("workers_queried", []),
            "degraded": data.get("degraded", False),
            "num_results": len(data.get("results", [])),
        }
    except Exception as exc:
        wall_ms = (time.perf_counter() - t0) * 1000
        return {
            "success": False,
            "wall_ms": wall_ms,
            "error": str(exc),
        }


async def run_benchmark(
    base_url: str,
    n_queries: int,
    top_k: int,
    concurrency: int,
) -> None:
    print(f"\n{'='*60}")
    print(f"  Distributed Semantic Search Engine — Benchmark")
    print(f"{'='*60}")
    print(f"  Target:      {base_url}")
    print(f"  Queries:     {n_queries}")
    print(f"  Top-K:       {top_k}")
    print(f"  Concurrency: {concurrency}")
    print(f"{'='*60}\n")

    # Check coordinator health
    async with httpx.AsyncClient() as client:
        try:
            health_resp = await client.get(f"{base_url}/health", timeout=5.0)
            health = health_resp.json()
            print(f"  Coordinator status: {health.get('status')}")
            print(f"  Healthy workers:    {health.get('healthy_worker_count')}/{health.get('total_worker_count')}")
            if health.get("degraded"):
                print("  ⚠  Running in DEGRADED mode\n")
        except Exception as e:
            print(f"  ⚠  Could not reach coordinator: {e}\n")

    semaphore = asyncio.Semaphore(concurrency)
    results = []
    queries = [random.choice(SAMPLE_QUERIES) for _ in range(n_queries)]

    async def run_with_semaphore(q: str) -> dict:
        async with semaphore:
            async with httpx.AsyncClient() as c:
                return await run_query(c, base_url, q, top_k)

    print("  Running queries…")
    t_start = time.perf_counter()
    tasks = [run_with_semaphore(q) for q in queries]
    results = await asyncio.gather(*tasks)
    total_elapsed = time.perf_counter() - t_start

    # Separate successes from failures
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    if not successes:
        print(f"\n  ERROR: All {n_queries} queries failed.")
        if failures:
            print(f"  First error: {failures[0].get('error')}")
        return

    wall_latencies = sorted(r["wall_ms"] for r in successes)
    server_latencies = sorted(r["total_latency_ms"] for r in successes)
    fanout_latencies = sorted(r["fanout_ms"] for r in successes)
    merge_latencies = sorted(r["merge_ms"] for r in successes)
    overhead_latencies = sorted(r["coordinator_overhead_ms"] for r in successes)

    qps = n_queries / total_elapsed
    degraded_count = sum(1 for r in successes if r.get("degraded"))

    # Worker query distribution
    worker_counts: dict[str, int] = {}
    for r in successes:
        for wid in r.get("workers_queried", []):
            worker_counts[wid] = worker_counts.get(wid, 0) + 1

    print(f"\n{'─'*60}")
    print("  RESULTS SUMMARY")
    print(f"{'─'*60}")
    print(f"  Total queries:    {n_queries}")
    print(f"  Successful:       {len(successes)} ({100*len(successes)/n_queries:.1f}%)")
    print(f"  Failed:           {len(failures)}")
    print(f"  Degraded mode:    {degraded_count} queries")
    print(f"  Elapsed time:     {total_elapsed:.2f}s")
    print(f"  Throughput:       {qps:.1f} QPS")
    print()

    print("  WALL-CLOCK LATENCY (client-side, includes network)")
    print(f"    p50:  {percentile(wall_latencies, 50):7.2f} ms")
    print(f"    p95:  {percentile(wall_latencies, 95):7.2f} ms")
    print(f"    p99:  {percentile(wall_latencies, 99):7.2f} ms")
    print(f"    min:  {wall_latencies[0]:7.2f} ms")
    print(f"    max:  {wall_latencies[-1]:7.2f} ms")
    print()

    print("  SERVER TOTAL LATENCY (coordinator-reported)")
    print(f"    p50:  {percentile(server_latencies, 50):7.2f} ms")
    print(f"    p95:  {percentile(server_latencies, 95):7.2f} ms")
    print(f"    p99:  {percentile(server_latencies, 99):7.2f} ms")
    print()

    print("  LATENCY BREAKDOWN (server-side, p50)")
    p50_idx = int(0.5 * len(successes))
    print(f"    Embed overhead:  {percentile(overhead_latencies, 50):7.2f} ms")
    print(f"    Fan-out time:    {percentile(fanout_latencies, 50):7.2f} ms")
    print(f"    Merge time:      {percentile(merge_latencies, 50):7.2f} ms")
    print()

    print("  PER-WORKER QUERY DISTRIBUTION")
    for wid, count in sorted(worker_counts.items()):
        pct = 100 * count / len(successes)
        bar = "█" * int(20 * count / max(worker_counts.values()))
        print(f"    {wid:<12} {bar:<20} {count} ({pct:.1f}%)")

    print()
    print("  WALL-CLOCK LATENCY HISTOGRAM")
    print_histogram(wall_latencies)
    print(f"\n{'='*60}\n")

    # SLA check
    p99 = percentile(wall_latencies, 99)
    sla_ok = p99 < 100.0
    print(f"  p99 SLA (<100ms): {'✓ PASS' if sla_ok else '✗ FAIL'} — {p99:.1f}ms")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the search coordinator")
    parser.add_argument("--url", default="http://localhost:8000", help="Coordinator base URL")
    parser.add_argument("--queries", type=int, default=1000, help="Number of queries to run")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K results per query")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent requests")
    args = parser.parse_args()

    asyncio.run(
        run_benchmark(
            base_url=args.url,
            n_queries=args.queries,
            top_k=args.top_k,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
