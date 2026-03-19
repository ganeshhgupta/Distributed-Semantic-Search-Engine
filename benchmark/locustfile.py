"""
Locust load test for the Distributed Semantic Search Engine coordinator.

Run with:
    locust -f benchmark/locustfile.py --host http://localhost:8000
    locust -f benchmark/locustfile.py --host http://localhost:8000 \
           --headless -u 100 -r 10 --run-time 60s

Scenarios:
    SearchUser   — normal search traffic (POST /search), weight 80
    HealthUser   — monitoring/health checks (GET /health, /metrics), weight 15
    BurstUser    — rapid-fire top-1 queries for latency profiling, weight 5
"""
from __future__ import annotations

import random
from typing import Optional

from locust import FastHttpUser, HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Sample query pool
# ---------------------------------------------------------------------------

QUERIES = [
    "quantum computing applications",
    "history of ancient Rome",
    "machine learning neural networks",
    "climate change sea level rise",
    "Renaissance art Leonardo da Vinci",
    "black holes Stephen Hawking",
    "World War II D-Day invasion",
    "protein folding AlphaFold",
    "Egyptian pharaohs pyramids",
    "deep learning image recognition",
    "Industrial Revolution steam engine",
    "CRISPR gene therapy cancer",
    "philosophy of mind consciousness",
    "Apollo moon landing NASA",
    "coral reef bleaching ocean warming",
    "Byzantine art mosaics Constantinople",
    "semiconductor silicon chip fabrication",
    "Hamlet Shakespeare tragedy",
    "polio vaccine Jonas Salk",
    "Bitcoin Ethereum blockchain consensus",
    "French Revolution Bastille storming",
    "superconductors high temperature",
    "Genghis Khan Mongol conquests",
    "hippocampus memory consolidation sleep",
    "solar panels renewable energy costs",
    "Ottoman sultans Istanbul",
    "Antarctic ice cores climate history",
    "AGI alignment safety risks",
    "feudalism serfdom medieval economy",
    "mRNA vaccines immune response",
    "dark matter cosmology evidence",
    "Amazon rainforest deforestation causes",
    "Silk Road trade goods ancient China",
    "Turing test artificial intelligence",
    "plate tectonics earthquakes volcanoes",
    "nuclear fusion ITER tokamak",
    "impressionism Monet Paris art movement",
    "penicillin Fleming antibiotic discovery",
    "Roman aqueducts engineering",
    "photosynthesis chlorophyll light reactions",
]


def random_query() -> str:
    return random.choice(QUERIES)


def random_top_k() -> int:
    return random.choice([5, 10, 10, 10, 20])  # bias toward 10


# ---------------------------------------------------------------------------
# Locust Users
# ---------------------------------------------------------------------------

class SearchUser(FastHttpUser):
    """
    Normal search traffic — POST /search with realistic query mix.
    Represents end-user search sessions.
    """

    weight = 80
    wait_time = between(0.1, 0.5)

    @task(10)
    def search_top10(self) -> None:
        payload = {"query": random_query(), "top_k": 10}
        with self.client.post(
            "/search",
            json=payload,
            name="/search (top_k=10)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                latency = data.get("total_latency_ms", 0)
                if latency > 500:
                    resp.failure(f"Slow response: {latency:.1f}ms")
                else:
                    resp.success()
            elif resp.status_code == 503:
                resp.failure("All workers down (503)")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(3)
    def search_top5(self) -> None:
        payload = {"query": random_query(), "top_k": 5}
        self.client.post("/search", json=payload, name="/search (top_k=5)")

    @task(1)
    def search_top20(self) -> None:
        payload = {"query": random_query(), "top_k": 20}
        self.client.post("/search", json=payload, name="/search (top_k=20)")


class HealthUser(FastHttpUser):
    """
    Monitoring traffic — polls health and metrics endpoints.
    Simulates a dashboard or alerting system.
    """

    weight = 15
    wait_time = between(1.0, 5.0)

    @task(3)
    def check_health(self) -> None:
        self.client.get("/health", name="/health")

    @task(2)
    def check_metrics(self) -> None:
        self.client.get("/metrics", name="/metrics")

    @task(1)
    def check_nodes(self) -> None:
        self.client.get("/nodes", name="/nodes")


class BurstUser(FastHttpUser):
    """
    Burst traffic — rapid low-top-k queries to stress the fan-out path.
    Simulates autocomplete or query-as-you-type scenarios.
    """

    weight = 5
    wait_time = between(0.0, 0.05)  # near zero think time

    @task
    def autocomplete_search(self) -> None:
        # Short prefix query
        query = random_query()[:20]
        payload = {"query": query, "top_k": 3}
        with self.client.post(
            "/search",
            json=payload,
            name="/search (burst top_k=3)",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")


# ---------------------------------------------------------------------------
# Event hooks — log aggregate stats on test stop
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quit(environment, **kwargs) -> None:  # type: ignore[type-arg]
    stats = environment.stats.total
    if stats.num_requests == 0:
        return

    print("\n" + "=" * 60)
    print("  Locust Run Summary")
    print("=" * 60)
    print(f"  Total requests:   {stats.num_requests}")
    print(f"  Failures:         {stats.num_failures} ({100*stats.fail_ratio:.1f}%)")
    print(f"  Median latency:   {stats.median_response_time:.1f} ms")
    print(f"  95th percentile:  {stats.get_response_time_percentile(0.95):.1f} ms")
    print(f"  99th percentile:  {stats.get_response_time_percentile(0.99):.1f} ms")
    print(f"  Max latency:      {stats.max_response_time:.1f} ms")
    print(f"  Requests/sec:     {stats.current_rps:.1f}")
    print("=" * 60 + "\n")
