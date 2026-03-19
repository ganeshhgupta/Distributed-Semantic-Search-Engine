"""
Embedding utilities for the worker node.

Wraps sentence-transformers to produce normalized L2 embeddings suitable
for inner-product (cosine) search with FAISS IndexFlatIP.
"""
from __future__ import annotations

import logging
import time
from typing import List, Union

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # dimension produced by all-MiniLM-L6-v2


class Embedder:
    """
    Thin wrapper around SentenceTransformer that always returns
    L2-normalized float32 numpy arrays.
    """

    def __init__(self, model_name: str = MODEL_NAME, device: str = "cpu") -> None:
        logger.info("Loading embedding model: %s on %s", model_name, device)
        t0 = time.perf_counter()
        self._model = SentenceTransformer(model_name, device=device)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Model loaded in %.1f ms", elapsed)
        self.dim = EMBEDDING_DIM
        self.model_name = model_name

    def embed(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 256,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Embed one or more texts.

        Returns:
            np.ndarray of shape (N, dim) with dtype float32, L2-normalized.
        """
        if isinstance(texts, str):
            texts = [texts]

        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize in place
        )

        # Ensure float32 (sentence-transformers may return float32 already,
        # but FAISS requires it explicitly)
        return embeddings.astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single query string.

        Returns:
            np.ndarray of shape (1, dim) with dtype float32, L2-normalized.
        """
        return self.embed(query)
