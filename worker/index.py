"""
FAISS index management for a single worker shard.

At runtime, workers only load pre-computed embeddings from disk —
they do NOT run sentence-transformers (saving ~350MB RAM on free tier).
Embeddings are baked into the Docker image at build time by
scripts/precompute_shard.py.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:
    import sys
    print("faiss-cpu is required: pip install faiss-cpu", file=sys.stderr)
    raise

logger = logging.getLogger(__name__)

EMBEDDINGS_FILE = "embeddings.npy"
METADATA_FILE = "metadata.json"


class ShardIndex:
    """
    FAISS-backed index for one pre-computed document shard.

    Load path (runtime):
        embeddings.npy  →  IndexFlatIP  +  metadata.json
    """

    def __init__(self, shard_id: int, worker_id: str, shard_dir: Path) -> None:
        self.shard_id = shard_id
        self.worker_id = worker_id
        self.shard_dir = shard_dir

        self._index: Optional[faiss.Index] = None
        self._metadata: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._doc_count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load pre-built shard from disk into a FAISS index."""
        emb_path = self.shard_dir / EMBEDDINGS_FILE
        meta_path = self.shard_dir / METADATA_FILE

        if not emb_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Pre-built shard not found at {self.shard_dir}. "
                "Was the Docker image built with scripts/precompute_shard.py?"
            )

        logger.info("[worker=%s shard=%d] Loading pre-built shard from %s",
                    self.worker_id, self.shard_id, self.shard_dir)
        t0 = time.perf_counter()

        self._embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self._metadata = json.load(f)

        self._doc_count = len(self._metadata)
        self._index = self._make_index(self._embeddings)

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[worker=%s shard=%d] Loaded %d docs in %.1f ms",
                    self.worker_id, self.shard_id, self._doc_count, elapsed)

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        """Run top-K nearest-neighbour search against the local FAISS index."""
        if self._index is None:
            raise RuntimeError("Index not loaded — call load() first")

        vec = query_embedding.astype(np.float32)
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)

        k = min(top_k, self._doc_count)
        if k == 0:
            return []

        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._metadata[idx]
            results.append({
                "doc_id": meta["doc_id"],
                "score": float(score),
                "text": meta["text"],
                "worker_id": self.worker_id,
                "shard_id": self.shard_id,
            })
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        return self._doc_count

    @property
    def index_size_bytes(self) -> int:
        return int(self._embeddings.nbytes) if self._embeddings is not None else 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_index(embeddings: np.ndarray) -> faiss.Index:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        return index
