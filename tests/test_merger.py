"""
Unit tests for the result merger.

Tests:
  - Correct top-K after merging results from multiple workers
  - De-duplication of doc_ids that appear in multiple worker responses
  - Correct rank assignment
  - Empty worker responses
  - Fewer than top_k total results
  - Both merge strategies (merge_results and merge_results_streaming) agree
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coordinator.merger import merge_results, merge_results_streaming
from shared.schemas import WorkerSearchResponse, WorkerSearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_worker_response(
    worker_id: str,
    shard_id: int,
    results: list[tuple[str, float, str]],  # (doc_id, score, text)
) -> WorkerSearchResponse:
    """Build a WorkerSearchResponse from a list of (doc_id, score, text) tuples."""
    return WorkerSearchResponse(
        results=[
            WorkerSearchResult(
                doc_id=doc_id,
                score=score,
                text=text,
                worker_id=worker_id,
                shard_id=shard_id,
            )
            for doc_id, score, text in results
        ],
        worker_id=worker_id,
        shard_id=shard_id,
        latency_ms=5.0,
        trace_id="test-trace",
    )


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------

class TestMergeBasic:
    def test_returns_top_k(self) -> None:
        r1 = make_worker_response("w1", 0, [
            ("d1", 0.9, "text1"),
            ("d2", 0.7, "text2"),
            ("d3", 0.5, "text3"),
        ])
        r2 = make_worker_response("w2", 1, [
            ("d4", 0.85, "text4"),
            ("d5", 0.6, "text5"),
        ])
        merged = merge_results([r1, r2], top_k=3)
        assert len(merged) == 3

    def test_sorted_by_score_descending(self) -> None:
        r1 = make_worker_response("w1", 0, [
            ("d1", 0.9, "t1"),
            ("d2", 0.3, "t2"),
        ])
        r2 = make_worker_response("w2", 1, [
            ("d3", 0.7, "t3"),
            ("d4", 0.5, "t4"),
        ])
        merged = merge_results([r1, r2], top_k=4)
        scores = [r.score for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_rank_is_1_indexed(self) -> None:
        r = make_worker_response("w1", 0, [("d1", 0.9, "t"), ("d2", 0.8, "t")])
        merged = merge_results([r], top_k=5)
        ranks = [m.rank for m in merged]
        assert ranks == list(range(1, len(merged) + 1))

    def test_correct_top_k_doc_ids(self) -> None:
        """The top-K highest-scoring docs should win."""
        r1 = make_worker_response("w1", 0, [
            ("high", 0.99, "t"),
            ("low",  0.10, "t"),
        ])
        r2 = make_worker_response("w2", 1, [
            ("mid",  0.55, "t"),
            ("vlow", 0.01, "t"),
        ])
        merged = merge_results([r1, r2], top_k=2)
        doc_ids = {m.doc_id for m in merged}
        assert doc_ids == {"high", "mid"}


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_doc_id_appears_once(self) -> None:
        """Same doc_id from two workers should appear only once in the output."""
        r1 = make_worker_response("w1", 0, [("shared", 0.9, "t")])
        r2 = make_worker_response("w2", 1, [("shared", 0.8, "t"), ("unique", 0.5, "t")])
        merged = merge_results([r1, r2], top_k=5)
        doc_ids = [m.doc_id for m in merged]
        assert doc_ids.count("shared") == 1

    def test_higher_score_copy_wins(self) -> None:
        """When a doc appears in multiple responses, the higher score should be kept."""
        r1 = make_worker_response("w1", 0, [("doc", 0.9, "high")])
        r2 = make_worker_response("w2", 1, [("doc", 0.5, "low")])
        merged = merge_results([r1, r2], top_k=3)
        doc_result = next(m for m in merged if m.doc_id == "doc")
        assert doc_result.score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_worker_list(self) -> None:
        merged = merge_results([], top_k=10)
        assert merged == []

    def test_all_workers_returned_empty(self) -> None:
        r1 = make_worker_response("w1", 0, [])
        r2 = make_worker_response("w2", 1, [])
        merged = merge_results([r1, r2], top_k=5)
        assert merged == []

    def test_fewer_results_than_top_k(self) -> None:
        r = make_worker_response("w1", 0, [("d1", 0.9, "t"), ("d2", 0.8, "t")])
        merged = merge_results([r], top_k=10)
        assert len(merged) == 2

    def test_single_worker(self) -> None:
        r = make_worker_response("w1", 0, [
            ("d1", 0.9, "t1"),
            ("d2", 0.7, "t2"),
            ("d3", 0.5, "t3"),
        ])
        merged = merge_results([r], top_k=2)
        assert len(merged) == 2
        assert merged[0].doc_id == "d1"
        assert merged[1].doc_id == "d2"

    def test_top_k_zero(self) -> None:
        r = make_worker_response("w1", 0, [("d1", 0.9, "t")])
        merged = merge_results([r], top_k=0)
        assert merged == []

    def test_metadata_preserved(self) -> None:
        """Worker_id and shard_id should be preserved in merged results."""
        r = make_worker_response("worker-2", 1, [("doc1", 0.8, "some text")])
        merged = merge_results([r], top_k=5)
        assert merged[0].worker_id == "worker-2"
        assert merged[0].shard_id == 1
        assert merged[0].text == "some text"


# ---------------------------------------------------------------------------
# Strategy agreement
# ---------------------------------------------------------------------------

class TestStrategyAgreement:
    """Both merge_results and merge_results_streaming must produce the same output."""

    def _make_responses(self) -> list[WorkerSearchResponse]:
        return [
            make_worker_response("w1", 0, [
                ("a", 0.95, "t"),
                ("b", 0.80, "t"),
                ("c", 0.60, "t"),
            ]),
            make_worker_response("w2", 1, [
                ("d", 0.90, "t"),
                ("e", 0.75, "t"),
                ("f", 0.50, "t"),
            ]),
            make_worker_response("w3", 2, [
                ("g", 0.88, "t"),
                ("h", 0.70, "t"),
                ("i", 0.40, "t"),
            ]),
        ]

    def test_both_strategies_agree(self) -> None:
        responses = self._make_responses()
        r1 = merge_results(responses, top_k=5)
        r2 = merge_results_streaming(responses, top_k=5)
        assert [r.doc_id for r in r1] == [r.doc_id for r in r2]
        assert [r.score for r in r1] == [r.score for r in r2]

    def test_strategies_agree_with_duplicates(self) -> None:
        responses = [
            make_worker_response("w1", 0, [("shared", 0.9, "t"), ("a", 0.5, "t")]),
            make_worker_response("w2", 1, [("shared", 0.8, "t"), ("b", 0.6, "t")]),
        ]
        r1 = merge_results(responses, top_k=3)
        r2 = merge_results_streaming(responses, top_k=3)
        # Both should have the same doc_ids (order may differ for ties)
        assert {r.doc_id for r in r1} == {r.doc_id for r in r2}
