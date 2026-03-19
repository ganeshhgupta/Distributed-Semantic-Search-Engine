"""
Runs at Docker BUILD time to pre-compute embeddings for one shard.

Fetches Wikipedia articles via the free REST API (no key needed).
Each shard gets articles from domain-specific categories so the
corpus is thematically diverse across workers.

SHARD_ID=0  →  Science & Technology
SHARD_ID=1  →  History & Society
SHARD_ID=2  →  Culture & World

Output:  /app/data/shard_{SHARD_ID}/embeddings.npy
         /app/data/shard_{SHARD_ID}/metadata.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SHARD_ID      = int(os.environ.get("SHARD_ID", "0"))
SHARD_COUNT   = int(os.environ.get("SHARD_COUNT", "3"))
TARGET_DOCS   = int(os.environ.get("DOCS_PER_SHARD", "1500"))
OUTPUT_DIR    = f"/app/data/shard_{SHARD_ID}"
MODEL_NAME    = "all-MiniLM-L6-v2"
MAX_WORKERS   = 12          # concurrent HTTP requests
MIN_WORDS     = 40          # skip stubs shorter than this
CHUNK_WORDS   = 220         # target words per chunk
WIKI_REST     = "https://en.wikipedia.org/api/rest_v1"
WIKI_API      = "https://en.wikipedia.org/w/api.php"
SESSION       = requests.Session()
SESSION.headers.update({"User-Agent": "SearchOS-PortfolioProject/1.0 (build-time indexer)"})

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Per-shard domain categories
# ---------------------------------------------------------------------------

SHARD_DOMAINS: Dict[int, Dict[str, Any]] = {
    0: {
        "label": "Science & Technology",
        "categories": [
            "Physics", "Chemistry", "Biology", "Mathematics",
            "Computer_science", "Astronomy", "Medicine",
            "Electrical_engineering", "Neuroscience", "Ecology",
            "Genetics", "Quantum_mechanics", "Thermodynamics",
        ],
    },
    1: {
        "label": "History & Society",
        "categories": [
            "World_War_II", "Ancient_Rome", "Ancient_Greece",
            "Industrial_Revolution", "Renaissance", "Cold_War",
            "French_Revolution", "Colonialism", "American_history",
            "Ancient_Egypt", "Byzantine_Empire", "Mongol_Empire",
            "Medieval_history",
        ],
    },
    2: {
        "label": "Culture & World",
        "categories": [
            "Geography", "Classical_music", "Western_philosophy",
            "World_literature", "Architecture", "Association_football",
            "World_religions", "Film", "Economics",
            "Political_philosophy", "Linguistics", "Mythology",
            "Visual_arts",
        ],
    },
}


# ---------------------------------------------------------------------------
# Wikipedia fetchers
# ---------------------------------------------------------------------------

def get_category_members(category: str, limit: int = 200) -> List[str]:
    """Return article titles in a Wikipedia category."""
    try:
        resp = SESSION.get(WIKI_API, params={
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": limit,
            "cmtype": "page",
            "format": "json",
        }, timeout=15)
        data = resp.json()
        return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
    except Exception as e:
        print(f"  [warn] category {category}: {e}")
        return []


def get_article_text(title: str) -> Optional[Dict[str, str]]:
    """
    Fetch plain-text article extract from Wikipedia API.
    Returns None if the article is a redirect, stub, or disambiguation.
    """
    try:
        resp = SESSION.get(WIKI_API, params={
            "action": "query",
            "prop": "extracts",
            "explaintext": True,
            "exsectionformat": "plain",
            "titles": title,
            "format": "json",
            "redirects": 1,
        }, timeout=15)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()))

        if "missing" in page:
            return None

        extract: str = page.get("extract", "").strip()
        # Skip disambiguation pages and stubs
        if "may refer to:" in extract or "disambiguation" in extract.lower():
            return None
        words = extract.split()
        if len(words) < MIN_WORDS:
            return None

        return {"title": title, "text": extract}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def chunk_article(title: str, text: str, shard_id: int, article_idx: int) -> List[Dict[str, str]]:
    """Split article text into ~CHUNK_WORDS word chunks."""
    words = text.split()
    chunks = []
    for chunk_i, start in enumerate(range(0, len(words), CHUNK_WORDS)):
        segment = words[start: start + CHUNK_WORDS]
        if len(segment) < MIN_WORDS:
            continue
        doc_id = f"wiki-s{shard_id}-{article_idx:05d}-c{chunk_i:02d}"
        chunk_text = f"{title}: {' '.join(segment)}"
        chunks.append({"doc_id": doc_id, "title": title, "text": chunk_text})
    return chunks


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_shard() -> None:
    domain = SHARD_DOMAINS.get(SHARD_ID, SHARD_DOMAINS[0])
    print(f"\n[precompute] shard={SHARD_ID} | domain='{domain['label']}' | target={TARGET_DOCS} docs")
    print(f"[precompute] output → {OUTPUT_DIR}")

    # ── Collect article titles from categories ─────────────────────────────
    print("[precompute] Fetching article titles from Wikipedia categories …")
    all_titles: List[str] = []
    seen: set = set()

    for cat in domain["categories"]:
        members = get_category_members(cat, limit=200)
        for t in members:
            if t not in seen:
                seen.add(t)
                all_titles.append(t)
        print(f"  {cat}: {len(members)} titles → running total {len(all_titles)}")

    # Shuffle for variety, then pad with random articles if needed
    random.shuffle(all_titles)
    print(f"[precompute] {len(all_titles)} unique titles from categories")

    # ── Fetch article texts concurrently ───────────────────────────────────
    print(f"[precompute] Fetching article texts (up to {len(all_titles)} articles) …")
    articles: List[Dict[str, str]] = []
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(get_article_text, title): title for title in all_titles}
        for future in as_completed(futures):
            result = future.result()
            if result:
                articles.append(result)
            if len(articles) % 100 == 0 and len(articles) > 0:
                print(f"  fetched {len(articles)} articles …")

    print(f"[precompute] Fetched {len(articles)} valid articles in {time.perf_counter()-t0:.1f}s")

    # ── Fill gaps with random Wikipedia articles if we have too few ─────────
    if len(articles) < TARGET_DOCS // 3:
        print(f"[precompute] Low article count — supplementing with random articles …")

        def fetch_random() -> Optional[Dict[str, str]]:
            try:
                r = SESSION.get(f"{WIKI_REST}/page/random/summary", timeout=10)
                d = r.json()
                extract = d.get("extract", "")
                if len(extract.split()) < MIN_WORDS:
                    return None
                return {"title": d.get("title", "Unknown"), "text": extract}
            except Exception:
                return None

        needed = (TARGET_DOCS // 3) - len(articles)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = [pool.submit(fetch_random) for _ in range(needed * 3)]
            for future in as_completed(futures):
                r = future.result()
                if r:
                    articles.append(r)
                if len(articles) >= TARGET_DOCS // 2:
                    break

    # ── Chunk articles ─────────────────────────────────────────────────────
    print("[precompute] Chunking articles …")
    documents: List[Dict[str, str]] = []
    for article_idx, article in enumerate(articles):
        chunks = chunk_article(
            article["title"], article["text"], SHARD_ID, article_idx
        )
        documents.extend(chunks)

    print(f"[precompute] {len(documents)} chunks from {len(articles)} articles")

    # Trim if we exceeded target
    if len(documents) > TARGET_DOCS:
        documents = documents[:TARGET_DOCS]
        print(f"[precompute] Trimmed to {TARGET_DOCS} chunks")

    if not documents:
        print("[precompute] ERROR: No documents produced — exiting")
        sys.exit(1)

    # ── Embed ──────────────────────────────────────────────────────────────
    print(f"[precompute] Loading model: {MODEL_NAME} …")
    model = SentenceTransformer(MODEL_NAME)

    print(f"[precompute] Embedding {len(documents)} chunks …")
    t1 = time.perf_counter()
    texts = [d["text"] for d in documents]
    embeddings = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    print(f"[precompute] Embedding done in {time.perf_counter()-t1:.1f}s — shape {embeddings.shape}")

    # ── Save ───────────────────────────────────────────────────────────────
    emb_path  = os.path.join(OUTPUT_DIR, "embeddings.npy")
    meta_path = os.path.join(OUTPUT_DIR, "metadata.json")
    domain_path = os.path.join(OUTPUT_DIR, "domain.json")

    np.save(emb_path, embeddings)

    # Save metadata (strip heavy text for memory efficiency, keep full for search)
    meta = [
        {"doc_id": d["doc_id"], "title": d.get("title", ""), "text": d["text"]}
        for d in documents
    ]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    # Save domain info for the corpus browser
    with open(domain_path, "w", encoding="utf-8") as f:
        json.dump({
            "shard_id": SHARD_ID,
            "label": domain["label"],
            "doc_count": len(documents),
            "article_count": len(articles),
            "categories": domain["categories"],
        }, f)

    print(f"\n[precompute] Shard {SHARD_ID} complete:")
    print(f"  articles : {len(articles)}")
    print(f"  chunks   : {len(documents)}")
    print(f"  emb size : {os.path.getsize(emb_path)/1024/1024:.1f} MB")
    print(f"  meta size: {os.path.getsize(meta_path)/1024:.1f} KB")


if __name__ == "__main__":
    build_shard()
