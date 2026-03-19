"""
Runs at Docker BUILD time to pre-compute embeddings for one shard.

Reads SHARD_ID, SHARD_COUNT, DOCS_PER_SHARD from environment.
Downloads the SQuAD dataset (fast, no streaming needed),
assigns rows to shards by round-robin index, embeds, and saves
embeddings.npy + metadata.json into /app/data/shard_{SHARD_ID}/.

This script is intentionally self-contained (no local imports)
so it can run before the package structure is fully set up.
"""
import json
import os
import sys
import time

import numpy as np
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

SHARD_ID = int(os.environ.get("SHARD_ID", "0"))
SHARD_COUNT = int(os.environ.get("SHARD_COUNT", "3"))
DOCS_PER_SHARD = int(os.environ.get("DOCS_PER_SHARD", "300"))
OUTPUT_DIR = f"/app/data/shard_{SHARD_ID}"
MODEL_NAME = "all-MiniLM-L6-v2"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"[precompute] shard={SHARD_ID}/{SHARD_COUNT}, target={DOCS_PER_SHARD} docs")
print(f"[precompute] output → {OUTPUT_DIR}")

# ── Load dataset ─────────────────────────────────────────────────────────────
print("[precompute] Downloading SQuAD dataset …")
t0 = time.perf_counter()
dataset = load_dataset("rajpurkar/squad", split="train", trust_remote_code=False)
print(f"[precompute] Dataset loaded in {time.perf_counter()-t0:.1f}s ({len(dataset)} rows)")

# ── Assign rows to this shard ─────────────────────────────────────────────────
# Use a set to deduplicate identical contexts (SQuAD has many Q&A per context).
seen_contexts: set = set()
documents = []

for i, row in enumerate(dataset):
    if i % SHARD_COUNT != SHARD_ID:
        continue
    ctx: str = row["context"]
    if ctx in seen_contexts:
        continue
    seen_contexts.add(ctx)
    title: str = row.get("title", "")
    doc_id = f"squad-s{SHARD_ID}-{len(documents):05d}"
    # Prepend title so semantic search surfaces the topic
    text = f"{title}: {ctx}" if title else ctx
    documents.append({"doc_id": doc_id, "text": text})
    if len(documents) >= DOCS_PER_SHARD:
        break

print(f"[precompute] Collected {len(documents)} unique docs for shard {SHARD_ID}")

if not documents:
    print("[precompute] ERROR: No documents collected — check SHARD_ID/SHARD_COUNT")
    sys.exit(1)

# ── Embed ─────────────────────────────────────────────────────────────────────
print(f"[precompute] Loading embedding model: {MODEL_NAME} …")
model = SentenceTransformer(MODEL_NAME)

print(f"[precompute] Embedding {len(documents)} documents …")
t1 = time.perf_counter()
texts = [d["text"] for d in documents]
embeddings = model.encode(
    texts,
    batch_size=64,
    normalize_embeddings=True,
    show_progress_bar=True,
    convert_to_numpy=True,
)
embeddings = embeddings.astype(np.float32)
print(f"[precompute] Embedding done in {time.perf_counter()-t1:.1f}s — shape {embeddings.shape}")

# ── Save ──────────────────────────────────────────────────────────────────────
emb_path = os.path.join(OUTPUT_DIR, "embeddings.npy")
meta_path = os.path.join(OUTPUT_DIR, "metadata.json")

np.save(emb_path, embeddings)
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump([{"doc_id": d["doc_id"], "text": d["text"]} for d in documents], f, ensure_ascii=False)

print(f"[precompute] Saved {len(documents)} docs → {OUTPUT_DIR}")
print(f"[precompute] embeddings.npy  {os.path.getsize(emb_path)/1024:.1f} KB")
print(f"[precompute] metadata.json   {os.path.getsize(meta_path)/1024:.1f} KB")
print("[precompute] Done.")
