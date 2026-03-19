"""
Result merger for the coordinator.

Takes top-K result lists from multiple worker shards and produces a globally
ranked top-K list using a simple score-based max-heap merge.
"""
from __future__ import annotations

import heapq
from typing import List

from shared.schemas import SearchResultItem, WorkerSearchResponse


def merge_results(
    worker_responses: List[WorkerSearchResponse],
    top_k: int,
) -> List[SearchResultItem]:
    """
    Merge top-K result lists from multiple workers into a single globally
    ranked top-K list.

    Strategy:
      - Collect all results into a single pool.
      - Sort by score descending (scores are cosine similarities in [0, 1]
        for normalized inner product, so higher = better).
      - Deduplicate by doc_id (keep the higher-scored copy).
      - Return the top `top_k` results with rank assigned.

    Args:
        worker_responses: List of WorkerSearchResponse objects (may be empty
                          if a worker was down / returned no results).
        top_k: Maximum number of results to return.

    Returns:
        List of SearchResultItem sorted by descending score, up to top_k.
    """
    # Collect all candidate results
    seen_doc_ids: set[str] = set()
    candidates: List[tuple[float, str, str, str, int]] = []
    # tuple: (-score, doc_id, text, worker_id, shard_id)  — negative for min-heap

    for resp in worker_responses:
        for result in resp.results:
            if result.doc_id not in seen_doc_ids:
                seen_doc_ids.add(result.doc_id)
                # Negate score so heapq (min-heap) gives us the largest first
                heapq.heappush(
                    candidates,
                    (-result.score, result.doc_id, result.text, result.worker_id, result.shard_id),
                )

    # Extract top_k
    merged: List[SearchResultItem] = []
    rank = 1
    while candidates and rank <= top_k:
        neg_score, doc_id, text, worker_id, shard_id = heapq.heappop(candidates)
        merged.append(
            SearchResultItem(
                doc_id=doc_id,
                score=round(-neg_score, 6),
                text=text,
                worker_id=worker_id,
                shard_id=shard_id,
                rank=rank,
            )
        )
        rank += 1

    return merged


def merge_results_streaming(
    worker_responses: List[WorkerSearchResponse],
    top_k: int,
) -> List[SearchResultItem]:
    """
    Alternative merge using a fixed-size heap — O(N log K) instead of O(N log N).

    More efficient when total candidates >> top_k.
    """
    heap: List[tuple[float, int, WorkerSearchResponse, int]] = []
    # (score, tie_breaker, resp, result_idx)

    # Bootstrap: push the first result from each worker
    tie = 0
    iterators = []
    for resp in worker_responses:
        it = iter(resp.results)
        iterators.append(it)
        first = next(it, None)
        if first is not None:
            heapq.heappush(heap, (first.score, tie, resp, 0))
            tie += 1

    seen: set[str] = set()
    merged: List[SearchResultItem] = []
    rank = 1

    # Drain heap, always extending from the worker that just yielded
    while heap and rank <= top_k:
        score, _, resp, idx = heapq.heappop(heap)
        result = resp.results[idx]

        if result.doc_id not in seen:
            seen.add(result.doc_id)
            merged.append(
                SearchResultItem(
                    doc_id=result.doc_id,
                    score=round(result.score, 6),
                    text=result.text,
                    worker_id=result.worker_id,
                    shard_id=result.shard_id,
                    rank=rank,
                )
            )
            rank += 1

        next_idx = idx + 1
        if next_idx < len(resp.results):
            next_result = resp.results[next_idx]
            heapq.heappush(heap, (next_result.score, tie, resp, next_idx))
            tie += 1

    return merged
