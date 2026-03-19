import { useState } from "react";
import type { SearchResponse } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

interface UseSearchReturn {
  results: SearchResponse | null;
  loading: boolean;
  error: string | null;
  search: (query: string, topK?: number) => Promise<void>;
  clear: () => void;
}

export function useSearch(): UseSearchReturn {
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async (query: string, topK = 10): Promise<void> => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), top_k: topK }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Search failed (${response.status}): ${detail}`);
      }

      const data: SearchResponse = await response.json();
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setResults(null);
    setError(null);
  };

  return { results, loading, error, search, clear };
}
