import { useEffect, useRef, useState } from "react";
import type { HealthResponse } from "../types";

const API_BASE = "/api";
const POLL_INTERVAL_MS = 5000;

interface UseClusterHealthReturn {
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
}

export function useClusterHealth(): UseClusterHealthReturn {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data: HealthResponse = await response.json();
        setHealth(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch health");
      } finally {
        setLoading(false);
      }
    };

    fetchHealth();
    intervalRef.current = setInterval(fetchHealth, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { health, loading, error };
}
