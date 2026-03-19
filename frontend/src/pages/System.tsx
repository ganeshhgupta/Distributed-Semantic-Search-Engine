import { motion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import LatencyChart from "../components/LatencyChart";
import WorkerCard from "../components/WorkerCard";
import { useClusterHealth } from "../hooks/useClusterHealth";
import { useMetrics } from "../hooks/useMetrics";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const WORKER_BAR_COLORS: Record<string, string> = {
  "search-worker-0": "bg-blue-500",
  "search-worker-1": "bg-emerald-500",
  "search-worker-2": "bg-orange-500",
};

// ---------------------------------------------------------------------------
// Kill-worker button with countdown
// ---------------------------------------------------------------------------
function KillWorkerButton({ workerId, isDown }: { workerId: string; isDown: boolean }) {
  const [countdown, setCountdown] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const simulate = async () => {
    setBusy(true);
    try {
      await fetch(`${API_BASE}/admin/simulate-down/${workerId}`, { method: "POST" });
      let t = 30;
      setCountdown(t);
      const iv = setInterval(() => {
        t -= 1;
        setCountdown(t);
        if (t <= 0) { clearInterval(iv); setCountdown(null); }
      }, 1000);
    } catch {
      // ignore
    } finally {
      setBusy(false);
    }
  };

  const recover = async () => {
    await fetch(`${API_BASE}/admin/simulate-recover/${workerId}`, { method: "POST" });
    setCountdown(null);
  };

  if (isDown && countdown !== null) {
    return (
      <button
        onClick={recover}
        className="text-xs font-mono text-emerald-600 bg-emerald-50 border border-emerald-200
          rounded-full px-3 py-1 hover:bg-emerald-100 transition-colors"
      >
        Recover now ({countdown}s)
      </button>
    );
  }

  if (isDown) {
    return (
      <span className="text-xs font-mono text-red-400 bg-red-50 rounded-full px-3 py-1">
        Offline
      </span>
    );
  }

  return (
    <button
      onClick={simulate}
      disabled={busy || countdown !== null}
      className="text-xs font-mono text-red-600 bg-red-50 border border-red-200
        rounded-full px-3 py-1 hover:bg-red-100 transition-colors
        disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {countdown !== null ? `Recovering in ${countdown}s…` : "Simulate Down"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Dark mode toggle
// ---------------------------------------------------------------------------
function DarkModeToggle() {
  const [dark, setDark] = useState(false);
  return (
    <button
      onClick={() => {
        const next = !dark;
        setDark(next);
        document.documentElement.classList.toggle("dark", next);
      }}
      className="text-slate-500 hover:text-slate-800 transition-colors text-sm font-mono"
    >
      {dark ? "☀ Light" : "◐ Dark"}
    </button>
  );
}

const cardVariants = {
  hidden:  { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function System() {
  const { health, loading: healthLoading } = useClusterHealth();
  const { current, history }               = useMetrics();

  const workers      = health?.workers ?? [];
  const totalQueries = current?.per_worker_queries
    ? Object.values(current.per_worker_queries).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <motion.div
      className="min-h-screen bg-slate-50 dark:bg-slate-900"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <header className="sticky top-0 z-20 h-16 bg-white/80 dark:bg-slate-800/80
        backdrop-blur border-b border-slate-100 dark:border-slate-700
        flex items-center px-6 gap-4">
        <Link to="/" className="font-sans font-bold text-lg text-slate-900 dark:text-white
          tracking-tight hover:text-indigo-600 transition-colors">
          SearchOS
        </Link>
        <span className="text-slate-300 dark:text-slate-600 text-sm">·</span>
        <span className="text-slate-500 dark:text-slate-400 text-sm">System Dashboard</span>
        <div className="ml-auto flex items-center gap-4">
          {health?.degraded && (
            <span className="text-xs font-medium text-red-600 bg-red-50 rounded-full px-3 py-1 animate-pulse">
              ⚠ Degraded Mode
            </span>
          )}
          <DarkModeToggle />
          <Link to="/corpus" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">Corpus</Link>
          <Link to="/search" className="text-slate-500 hover:text-slate-800 text-sm transition-colors">Search</Link>
        </div>
      </header>

      {/* Demo banner */}
      <div className="bg-indigo-50 border-b border-indigo-100 px-6 py-2 flex items-center gap-2">
        <span className="text-xs text-indigo-600 font-medium">
          ⚡ Live fault-tolerance demo — click "Simulate Down" on any worker to see degraded mode in action. It auto-recovers in 30 s.
        </span>
      </div>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <motion.div
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
        >
          {/* ----------------------------------------------------------------
              LEFT — Cluster Health
          ---------------------------------------------------------------- */}
          <div className="space-y-4">
            <h2 className="text-slate-900 dark:text-white font-semibold text-base">Cluster Health</h2>

            {/* Coordinator card */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${health?.degraded ? "bg-amber-400" : "bg-emerald-500"}`} />
                    <span className="font-mono text-sm font-medium text-slate-700 dark:text-slate-200">
                      coordinator
                    </span>
                  </div>
                  {healthLoading ? (
                    <span className="text-xs text-slate-400">Polling…</span>
                  ) : (
                    <span className={`text-xs font-medium rounded-full px-2 py-0.5
                      ${health?.degraded ? "bg-amber-50 text-amber-600" : "bg-emerald-50 text-emerald-600"}`}>
                      {health?.status ?? "unknown"}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <p className="text-slate-400 text-xs">Uptime</p>
                    <p className="font-mono font-medium text-slate-800 dark:text-white">
                      {health ? `${Math.floor(health.uptime_seconds)}s` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Workers</p>
                    <p className="font-mono font-medium text-slate-800 dark:text-white">
                      {health ? `${health.healthy_worker_count}/${health.total_worker_count}` : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-xs">Mode</p>
                    <p className={`font-mono font-medium ${health?.degraded ? "text-amber-500" : "text-emerald-600"}`}>
                      {health?.degraded ? "degraded" : "normal"}
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Worker cards */}
            {workers.map((worker) => {
              const isDown = worker.status === "down" || !["healthy", "degraded"].includes(worker.status);
              return (
                <motion.div key={worker.worker_id} variants={cardVariants} transition={{ duration: 0.2 }}>
                  <div className={`bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                    dark:border-slate-700 shadow-sm p-5 transition-all duration-500
                    ${isDown ? "opacity-50 grayscale" : ""}`}>
                    <div className="flex items-center justify-between mb-3">
                      <WorkerCard
                        worker={worker}
                        queriesServed={current?.per_worker_queries?.[worker.worker_id] ?? 0}
                      />
                      <KillWorkerButton workerId={worker.worker_id} isDown={isDown} />
                    </div>
                  </div>
                </motion.div>
              );
            })}

            {workers.length === 0 && !healthLoading && (
              <p className="text-slate-400 text-sm text-center py-4">No worker data available.</p>
            )}
          </div>

          {/* ----------------------------------------------------------------
              RIGHT — Live Metrics
          ---------------------------------------------------------------- */}
          <div className="space-y-4">
            <h2 className="text-slate-900 dark:text-white font-semibold text-base">Live Metrics</h2>

            {/* Latency chart */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    Latency — p50 / p95 / p99
                  </p>
                  <span className="font-mono text-xs text-slate-400">last 60s</span>
                </div>
                {history.length > 1 ? (
                  <LatencyChart history={history} />
                ) : (
                  <div className="h-48 flex items-center justify-center text-slate-300 text-sm">
                    Waiting for queries…
                  </div>
                )}
              </div>
            </motion.div>

            {/* QPS */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <p className="text-xs text-slate-400 mb-1">Queries / sec</p>
                <p className="font-mono font-bold text-4xl text-slate-900 dark:text-white">
                  {current?.qps.toFixed(1) ?? "0.0"}
                </p>
                <div className="mt-2 flex gap-4 text-xs font-mono text-slate-400">
                  <span>total {current?.total_queries.toLocaleString() ?? 0}</span>
                  <span>errors {current?.error_count ?? 0}</span>
                  <span>degraded {current?.degraded_count ?? 0}</span>
                </div>
              </div>
            </motion.div>

            {/* Per-worker distribution */}
            <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
              <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                dark:border-slate-700 shadow-sm p-5">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-4">
                  Query Distribution
                </p>
                {totalQueries === 0 ? (
                  <p className="text-slate-300 text-sm">Run a search to see distribution.</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(current?.per_worker_queries ?? {}).map(([wid, count]) => {
                      const pct      = totalQueries > 0 ? (count / totalQueries) * 100 : 0;
                      const barColor = WORKER_BAR_COLORS[wid] ?? "bg-slate-400";
                      return (
                        <div key={wid}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-xs text-slate-600 dark:text-slate-300">{wid}</span>
                            <span className="font-mono text-xs text-slate-400">
                              {count.toLocaleString()} ({pct.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="w-full h-2 bg-slate-100 rounded-full">
                            <div className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
                              style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* p50/p95/p99 */}
            {current && (
              <motion.div variants={cardVariants} transition={{ duration: 0.2 }}>
                <div className="bg-white dark:bg-slate-800 rounded-[12px] border border-slate-100
                  dark:border-slate-700 shadow-sm p-5">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
                    Current Latency
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "p50", value: current.p50_ms, color: "text-indigo-500" },
                      { label: "p95", value: current.p95_ms, color: "text-amber-500" },
                      { label: "p99", value: current.p99_ms, color: "text-red-500" },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="text-center">
                        <p className="text-slate-400 text-xs mb-1 font-mono">{label}</p>
                        <p className={`font-mono font-bold text-xl ${color}`}>
                          {value.toFixed(1)}
                          <span className="text-xs font-normal text-slate-400 ml-0.5">ms</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </main>
    </motion.div>
  );
}
