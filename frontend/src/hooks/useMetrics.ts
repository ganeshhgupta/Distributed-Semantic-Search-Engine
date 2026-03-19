import { useEffect, useRef, useState } from "react";
import type { MetricsSnapshot } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const MAX_SNAPSHOTS = 60;
const POLL_INTERVAL_MS = 1000;

interface UseMetricsReturn {
  current: MetricsSnapshot | null;
  history: MetricsSnapshot[];
  error: string | null;
}

export function useMetrics(): UseMetricsReturn {
  const [current, setCurrent] = useState<MetricsSnapshot | null>(null);
  const [history, setHistory] = useState<MetricsSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${API_BASE}/metrics`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        setCurrent(data.current);
        setHistory((prev) => {
          const combined = [...prev, data.current];
          return combined.slice(-MAX_SNAPSHOTS);
        });
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch metrics");
      }
    };

    fetchMetrics();
    intervalRef.current = setInterval(fetchMetrics, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { current, history, error };
}
