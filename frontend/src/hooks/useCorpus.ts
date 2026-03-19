import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export interface CorpusDoc {
  doc_id: string;
  title: string;
  text: string;
  worker_id: string;
  shard_id: number;
  domain: string;
}

export interface CorpusShard {
  shard_id: number;
  worker_id: string;
  domain: { label: string; categories: string[]; doc_count: number };
  total_docs: number;
  documents: CorpusDoc[];
}

export interface CorpusData {
  shards: CorpusShard[];
  documents: CorpusDoc[];
  total_docs: number;
  healthy_shards: number;
}

interface UseCorpusReturn {
  data: CorpusData | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useCorpus(n = 18): UseCorpusReturn {
  const [data, setData]       = useState<CorpusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [tick, setTick]       = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/corpus/sample?n=${n}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: CorpusData) => {
        if (!cancelled) { setData(d); setError(null); }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [n, tick]);

  return { data, loading, error, refresh: () => setTick((t) => t + 1) };
}
