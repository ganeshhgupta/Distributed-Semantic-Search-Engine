"""
FAISS index for a single pre-computed worker shard.
Workers load embeddings baked in at Docker build time — no sentence-transformers at runtime.
"""
from __future__ import annotations

import json
import logging
import random
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
METADATA_FILE   = "metadata.json"
DOMAIN_FILE     = "domain.json"


class ShardIndex:
    def __init__(self, shard_id: int, worker_id: str, shard_dir: Path) -> None:
        self.shard_id  = shard_id
        self.worker_id = worker_id
        self.shard_dir = shard_dir

        self._index:      Optional[faiss.Index]        = None
        self._metadata:   List[Dict[str, Any]]         = []
        self._embeddings: Optional[np.ndarray]         = None
        self._domain:     Dict[str, Any]               = {}
        self._doc_count:  int                          = 0

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> None:
        emb_path    = self.shard_dir / EMBEDDINGS_FILE
        meta_path   = self.shard_dir / METADATA_FILE
        domain_path = self.shard_dir / DOMAIN_FILE

        if not emb_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Pre-built shard not found at {self.shard_dir}. "
                "Was the Docker image built with scripts/precompute_shard.py?"
            )

        t0 = time.perf_counter()
        self._embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self._metadata = json.load(f)
        if domain_path.exists():
            with open(domain_path, "r", encoding="utf-8") as f:
                self._domain = json.load(f)

        self._doc_count = len(self._metadata)
        self._index = self._make_index(self._embeddings)

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[worker=%s shard=%d] Loaded %d docs in %.1f ms",
                    self.worker_id, self.shard_id, self._doc_count, elapsed)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        if self._index is None:
            raise RuntimeError("Index not loaded")

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
                "doc_id":    meta["doc_id"],
                "score":     float(score),
                "text":      meta["text"],
                "title":     meta.get("title", ""),
                "worker_id": self.worker_id,
                "shard_id":  self.shard_id,
            })
        return results

    # ------------------------------------------------------------------
    # Corpus sample (for browser)
    # ------------------------------------------------------------------

    def sample(self, n: int = 20) -> List[Dict[str, Any]]:
        """Return n random documents for the corpus browser."""
        if not self._metadata:
            return []
        chosen = random.sample(self._metadata, min(n, len(self._metadata)))
        return [
            {
                "doc_id":    m["doc_id"],
                "title":     m.get("title", ""),
                "text":      m["text"][:300],   # snippet only
                "worker_id": self.worker_id,
                "shard_id":  self.shard_id,
                "domain":    self._domain.get("label", ""),
            }
            for m in chosen
        ]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        return self._doc_count

    @property
    def index_size_bytes(self) -> int:
        return int(self._embeddings.nbytes) if self._embeddings is not None else 0

    @property
    def domain(self) -> Dict[str, Any]:
        return self._domain

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_index(embeddings: np.ndarray) -> faiss.Index:
        dim   = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        return index
