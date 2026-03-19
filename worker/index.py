"""
FAISS index management for a single worker shard.

Responsibilities:
  - Load/save the shard to disk (numpy arrays + JSON metadata)
  - Build a FAISS IndexFlatIP (inner product = cosine on normalized vecs)
  - Execute top-K searches and return structured results
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# FAISS import with a helpful error message
try:
    import faiss  # type: ignore
except ImportError:
    print("faiss-cpu is required: pip install faiss-cpu", file=sys.stderr)
    raise

from worker.embedder import Embedder, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# File names inside the shard directory
EMBEDDINGS_FILE = "embeddings.npy"
METADATA_FILE = "metadata.json"


class ShardIndex:
    """
    A FAISS-backed index for one document shard.

    The on-disk layout under `shard_dir` is:
        embeddings.npy   — float32 array of shape (N, 384)
        metadata.json    — list of {doc_id, text} dicts
    """

    def __init__(
        self,
        shard_id: int,
        worker_id: str,
        shard_dir: Path,
        embedder: Embedder,
    ) -> None:
        self.shard_id = shard_id
        self.worker_id = worker_id
        self.shard_dir = shard_dir
        self._embedder = embedder

        # populated after load() or build()
        self._index: Optional[faiss.Index] = None
        self._metadata: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._doc_count: int = 0
        self._built_at: float = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_or_build(self, documents: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        If a saved shard exists on disk, reload it.  Otherwise build from
        `documents` (list of {doc_id, text} dicts) and persist it.
        """
        emb_path = self.shard_dir / EMBEDDINGS_FILE
        meta_path = self.shard_dir / METADATA_FILE

        if emb_path.exists() and meta_path.exists():
            logger.info("[worker=%s shard=%d] Loading shard from disk", self.worker_id, self.shard_id)
            self._load_from_disk(emb_path, meta_path)
        elif documents is not None:
            logger.info(
                "[worker=%s shard=%d] Building index for %d documents",
                self.worker_id, self.shard_id, len(documents),
            )
            self._build(documents)
            self._save_to_disk(emb_path, meta_path)
        else:
            raise RuntimeError(
                f"No shard on disk at {self.shard_dir} and no documents provided to build from"
            )

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Dict[str, Any]]:
        """
        Run a nearest-neighbour search against the local FAISS index.

        Args:
            query_embedding: float32 array of shape (1, dim) or (dim,)
            top_k: number of results to return

        Returns:
            List of dicts with keys: doc_id, score, text, worker_id, shard_id
        """
        if self._index is None:
            raise RuntimeError("Index not loaded — call load_or_build() first")

        vec = query_embedding.astype(np.float32)
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)

        k = min(top_k, self._doc_count)
        if k == 0:
            return []

        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty slots
                continue
            meta = self._metadata[idx]
            results.append(
                {
                    "doc_id": meta["doc_id"],
                    "score": float(score),
                    "text": meta["text"],
                    "worker_id": self.worker_id,
                    "shard_id": self.shard_id,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def document_count(self) -> int:
        return self._doc_count

    @property
    def index_size_bytes(self) -> int:
        """Rough in-memory size: embeddings array bytes."""
        if self._embeddings is None:
            return 0
        return int(self._embeddings.nbytes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build(self, documents: List[Dict[str, Any]]) -> None:
        texts = [d["text"] for d in documents]
        logger.info("[shard=%d] Embedding %d texts …", self.shard_id, len(texts))
        t0 = time.perf_counter()
        embeddings = self._embedder.embed(texts, show_progress=True)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("[shard=%d] Embedding done in %.1f ms", self.shard_id, elapsed)

        self._embeddings = embeddings
        self._metadata = [{"doc_id": d["doc_id"], "text": d["text"]} for d in documents]
        self._doc_count = len(documents)
        self._index = self._make_index(embeddings)
        self._built_at = time.time()

    def _load_from_disk(self, emb_path: Path, meta_path: Path) -> None:
        self._embeddings = np.load(str(emb_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            self._metadata = json.load(f)
        self._doc_count = len(self._metadata)
        self._index = self._make_index(self._embeddings)
        self._built_at = time.time()
        logger.info(
            "[shard=%d] Reloaded %d documents from disk", self.shard_id, self._doc_count
        )

    def _save_to_disk(self, emb_path: Path, meta_path: Path) -> None:
        self.shard_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(emb_path), self._embeddings)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False)
        logger.info("[shard=%d] Shard persisted to %s", self.shard_id, self.shard_dir)

    @staticmethod
    def _make_index(embeddings: np.ndarray) -> faiss.Index:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)  # inner product (cosine on normalized vecs)
        index.add(embeddings)
        return index
