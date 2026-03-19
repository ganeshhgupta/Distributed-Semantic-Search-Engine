"""
Unit tests for the consistent hash ring.

Tests:
  - Shard assignment is deterministic for the same key
  - All keys route to a valid registered node
  - Removing a node does not affect keys that were already on other nodes
  - Virtual node distribution is approximately uniform
  - Edge cases: single node, node add/remove
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from coordinator.hash_ring import ConsistentHashRing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ring_3() -> ConsistentHashRing:
    """A ring with 3 nodes, 150 vnodes each."""
    ring = ConsistentHashRing(vnodes=150)
    ring.add_node("worker-1")
    ring.add_node("worker-2")
    ring.add_node("worker-3")
    return ring


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_key_same_node(self, ring_3: ConsistentHashRing) -> None:
        """Calling get_node twice with the same key must return the same node."""
        keys = ["doc-0001", "wiki-12345", "article-xyz", "hello world", ""]
        for key in keys:
            first = ring_3.get_node(key)
            second = ring_3.get_node(key)
            assert first == second, f"Key '{key}' mapped to two different nodes"

    def test_assignment_stable_across_instances(self) -> None:
        """Two independently created rings with the same nodes must agree."""
        ring_a = ConsistentHashRing(vnodes=100)
        ring_b = ConsistentHashRing(vnodes=100)
        for node in ["alpha", "beta", "gamma"]:
            ring_a.add_node(node)
            ring_b.add_node(node)

        for key in [f"doc-{i}" for i in range(500)]:
            assert ring_a.get_node(key) == ring_b.get_node(key)

    def test_hash_is_md5_based(self) -> None:
        """Internal _hash must be deterministic across Python versions."""
        h = ConsistentHashRing._hash("test-key")
        assert isinstance(h, int)
        assert 0 <= h < ConsistentHashRing.RING_SIZE
        # Verify the exact value (MD5 is stable)
        import hashlib
        digest = hashlib.md5(b"test-key", usedforsecurity=False).digest()
        expected = int.from_bytes(digest[:4], byteorder="big")
        assert h == expected


# ---------------------------------------------------------------------------
# Node membership tests
# ---------------------------------------------------------------------------

class TestNodeMembership:
    def test_all_keys_route_to_valid_node(self, ring_3: ConsistentHashRing) -> None:
        valid_nodes = set(ring_3.get_nodes())
        for i in range(1000):
            node = ring_3.get_node(f"doc-{i:05d}")
            assert node in valid_nodes

    def test_empty_ring_returns_none(self) -> None:
        ring = ConsistentHashRing()
        assert ring.get_node("any-key") is None

    def test_single_node_all_keys_go_there(self) -> None:
        ring = ConsistentHashRing(vnodes=50)
        ring.add_node("solo")
        for i in range(200):
            assert ring.get_node(f"doc-{i}") == "solo"

    def test_get_nodes_reflects_added_nodes(self) -> None:
        ring = ConsistentHashRing()
        ring.add_node("n1")
        ring.add_node("n2")
        assert set(ring.get_nodes()) == {"n1", "n2"}

    def test_add_duplicate_node_raises(self) -> None:
        ring = ConsistentHashRing()
        ring.add_node("n1")
        with pytest.raises(ValueError, match="already in the ring"):
            ring.add_node("n1")

    def test_remove_missing_node_raises(self) -> None:
        ring = ConsistentHashRing()
        with pytest.raises(ValueError, match="not found in ring"):
            ring.remove_node("ghost")


# ---------------------------------------------------------------------------
# Removal stability tests
# ---------------------------------------------------------------------------

class TestRemoval:
    def test_remove_node_keys_reassign_to_remaining(self) -> None:
        """After removing a node, all keys must map to one of the remaining nodes."""
        ring = ConsistentHashRing(vnodes=100)
        ring.add_node("a")
        ring.add_node("b")
        ring.add_node("c")
        ring.remove_node("c")

        valid = {"a", "b"}
        for i in range(500):
            assert ring.get_node(f"key-{i}") in valid

    def test_keys_on_other_nodes_unchanged_after_removal(self) -> None:
        """
        Keys that were assigned to surviving nodes should (mostly) keep their
        assignment after another node is removed.  Consistent hashing guarantees
        only the keys formerly owned by the removed node migrate.
        """
        ring = ConsistentHashRing(vnodes=150)
        for node in ["n1", "n2", "n3"]:
            ring.add_node(node)

        keys = [f"doc-{i}" for i in range(300)]
        before = {k: ring.get_node(k) for k in keys}

        ring.remove_node("n3")

        after = {k: ring.get_node(k) for k in keys}
        changed = sum(1 for k in keys if before[k] != after[k] and before[k] != "n3")
        # Keys that used to be on n3 will change — that's expected.
        # Keys on n1 or n2 must NOT change (consistent hashing guarantee).
        assert changed == 0, f"{changed} keys on surviving nodes changed unexpectedly"

    def test_ring_empty_after_removing_all_nodes(self) -> None:
        ring = ConsistentHashRing(vnodes=50)
        ring.add_node("x")
        ring.add_node("y")
        ring.remove_node("x")
        ring.remove_node("y")
        assert ring.get_node("anything") is None
        assert len(ring) == 0


# ---------------------------------------------------------------------------
# Distribution tests
# ---------------------------------------------------------------------------

class TestDistribution:
    def test_vnode_counts_equal_per_node(self, ring_3: ConsistentHashRing) -> None:
        """Each node should have exactly `vnodes` virtual nodes."""
        stats = ring_3.distribution_stats()
        assert stats == {"worker-1": 150, "worker-2": 150, "worker-3": 150}

    def test_document_distribution_roughly_uniform(self, ring_3: ConsistentHashRing) -> None:
        """
        With 150 vnodes and 10 000 docs, each shard should own roughly 33%.
        We allow a ±10 pp tolerance.
        """
        counts: dict[str, int] = {}
        total = 10_000
        for i in range(total):
            node = ring_3.get_node(f"wiki-{i:07d}-chunk-000")
            counts[node] = counts.get(node, 0) + 1

        for node, count in counts.items():
            fraction = count / total
            assert 0.23 <= fraction <= 0.43, (
                f"Node {node} owns {fraction:.1%} of docs — outside ±10pp tolerance"
            )


# ---------------------------------------------------------------------------
# Shard ranges
# ---------------------------------------------------------------------------

class TestShardRanges:
    def test_shard_ranges_present_for_all_nodes(self, ring_3: ConsistentHashRing) -> None:
        ranges = ring_3.get_shard_ranges()
        assert set(ranges.keys()) == {"worker-1", "worker-2", "worker-3"}

    def test_shard_ranges_are_valid_tuples(self, ring_3: ConsistentHashRing) -> None:
        for node, (lo, hi) in ring_3.get_shard_ranges().items():
            assert isinstance(lo, int)
            assert isinstance(hi, int)
            assert lo <= hi, f"Node {node} has inverted shard range ({lo}, {hi})"
