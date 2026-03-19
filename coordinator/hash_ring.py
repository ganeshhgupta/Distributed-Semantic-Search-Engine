"""
Consistent hash ring for distributing documents across worker shards.

Uses MD5 for position computation and supports virtual nodes (vnodes) to
achieve a more uniform distribution across the ring.
"""
from __future__ import annotations

import hashlib
import bisect
from typing import Dict, List, Optional, Tuple


class ConsistentHashRing:
    """
    A consistent hash ring with virtual nodes.

    Each physical node (worker) is represented by `vnodes` virtual nodes
    distributed uniformly around the ring. A document's shard is determined
    by hashing its ID and walking clockwise to the next virtual node.
    """

    RING_SIZE = 2**32  # MD5 truncated to 32 bits

    def __init__(self, vnodes: int = 150) -> None:
        self.vnodes = vnodes
        # sorted list of (ring_position, node_id) tuples
        self._ring: List[Tuple[int, str]] = []
        # mapping from node_id -> list of positions
        self._node_positions: Dict[str, List[int]] = {}

    # ------------------------------------------------------------------
    # Ring management
    # ------------------------------------------------------------------

    def add_node(self, node_id: str) -> None:
        """Add a physical node and its virtual replicas to the ring."""
        if node_id in self._node_positions:
            raise ValueError(f"Node '{node_id}' is already in the ring")

        positions: List[int] = []
        for i in range(self.vnodes):
            key = f"{node_id}:vnode:{i}"
            pos = self._hash(key)
            positions.append(pos)
            bisect.insort(self._ring, (pos, node_id))

        self._node_positions[node_id] = positions

    def remove_node(self, node_id: str) -> None:
        """Remove a physical node and all its virtual nodes from the ring."""
        if node_id not in self._node_positions:
            raise ValueError(f"Node '{node_id}' not found in ring")

        positions = self._node_positions.pop(node_id)
        pos_set = set(positions)
        self._ring = [(pos, nid) for pos, nid in self._ring
                      if not (nid == node_id and pos in pos_set)]

    def get_node(self, key: str) -> Optional[str]:
        """
        Return the node responsible for the given key.

        Walks clockwise around the ring from the key's hash position.
        Returns None if the ring is empty.
        """
        if not self._ring:
            return None
        pos = self._hash(key)
        idx = bisect.bisect_left(self._ring, (pos, ""))
        if idx >= len(self._ring):
            idx = 0
        return self._ring[idx][1]

    def get_nodes(self) -> List[str]:
        """Return deduplicated list of physical node IDs currently in the ring."""
        return list(self._node_positions.keys())

    # ------------------------------------------------------------------
    # Shard assignment helpers
    # ------------------------------------------------------------------

    def assign_shard(self, doc_id: str) -> str:
        """Return the worker node responsible for doc_id."""
        node = self.get_node(doc_id)
        if node is None:
            raise RuntimeError("Hash ring is empty — no nodes registered")
        return node

    def get_shard_ranges(self) -> Dict[str, Tuple[int, int]]:
        """
        Compute the approximate ring coverage (min, max) for each node.

        This is used for informational display in GET /nodes; it is NOT
        a strict partition boundary.
        """
        if not self._ring:
            return {}

        ranges: Dict[str, List[int]] = {nid: [] for nid in self._node_positions}
        for pos, nid in self._ring:
            ranges[nid].append(pos)

        return {
            nid: (min(positions), max(positions))
            for nid, positions in ranges.items()
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(key: str) -> int:
        """Compute a 32-bit hash for a key using MD5."""
        digest = hashlib.md5(key.encode("utf-8"), usedforsecurity=False).digest()
        # Take the first 4 bytes as a big-endian unsigned int
        return int.from_bytes(digest[:4], byteorder="big")

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def distribution_stats(self) -> Dict[str, int]:
        """Return vnode count per physical node (for testing uniformity)."""
        counts: Dict[str, int] = {}
        for _, nid in self._ring:
            counts[nid] = counts.get(nid, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._ring)

    def __repr__(self) -> str:
        return (
            f"ConsistentHashRing(nodes={list(self._node_positions.keys())}, "
            f"vnodes={self.vnodes}, ring_size={len(self._ring)})"
        )
